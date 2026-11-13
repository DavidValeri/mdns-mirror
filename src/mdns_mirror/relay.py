"""The mDNS relay: sockets, the receive loop, and the forwarding path.

How it works:

1. For every network and IP family, one socket is bound to UDP port 5353
   on that interface only (SO_BINDTODEVICE) and joins the mDNS groups
   (224.0.0.251 and ff02::fb). A packet on that socket came in on that
   network. The same socket sends on that network, so forwarded packets
   keep source port 5353, as RFC 6762 requires.
2. Each received packet becomes a Message. decide() picks the output
   networks. Link-local address records are removed from the payload, and
   the rest of the payload is re-sent on each output network.
3. A packet stays within its IP family: IPv4 goes to IPv4 outputs and IPv6
   to IPv6 outputs. This matches Avahi's default.

Unicast traffic is handled separately. A QU query is relayed like a
multicast query, but with a relay-chosen ID, which is remembered for a short
time. A unicast reply with that ID is sent back to the querier with the
querier's original ID restored, if the rules allow it.

Legacy unicast (RFC 6762 section 6.7) is handled separately again. A query
sent from a port other than 5353 expects a unicast reply to that port. The
relay forwards it from a separate ephemeral socket on each output network
with a new ID, so responders reply to the relay. The relay then restores the
original ID and sends the reply to the querier.

Only Linux is supported. The interface binding and the multicast options
depend on Linux socket behavior.
"""

import fcntl
import ipaddress
import logging
import select
import socket
import struct
import time
from collections import namedtuple

from mdns_mirror.packet import classify, strip_link_local
from mdns_mirror.rules import Message, decide

log = logging.getLogger("mdns_mirror")
PORT = 5353
MDNS_V4 = "224.0.0.251"
MDNS_V6 = "ff02::fb"
# Linux ioctl that returns an interface's IPv4 address.
SIOCGIFADDR = 0x8915
# How long a relayed QU query stays eligible for a reply, in seconds.
QUERY_WINDOW = 5
# How long a relayed legacy query stays eligible for replies, in seconds.
# RFC 6762 and Avahi both use about two seconds.
LEGACY_WINDOW = 2

# A relayed QU query waiting for a reply. `source` is the querier's network,
# `querier` is its address there, `original_id` is the ID the querier chose,
# and `expires` is a time.monotonic() value.
Pending = namedtuple("Pending", "source querier original_id expires")

# A relayed legacy query waiting for replies. `port` and `original_id` are
# the querier's, which the reply must go back to.
Legacy = namedtuple("Legacy", "source querier port original_id expires")


def interface_index(name):
    """Look up the kernel's numeric index for a network interface.

    Args:
        name: Interface name, such as "eth0".

    Returns:
        The integer interface index.
    """
    return socket.if_nametoindex(name)


def interface_addresses(name):
    """List every IPv4 and IPv6 address on an interface.

    Used for the loop check. IPv4 comes from an ioctl; IPv6 comes from
    /proc/net/if_inet6, which lists each address as 32 hex digits.

    Args:
        name: Interface name, such as "eth0".

    Returns:
        A set of address strings. Empty if the interface has none.
    """
    addresses = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            reply = fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack("256s", name.encode()))
            # The address sits at byte 20 of the returned ifreq structure.
            addresses.add(socket.inet_ntoa(reply[20:24]))
        except OSError:
            pass
    with open("/proc/net/if_inet6") as f:
        for line in f:
            fields = line.split()
            if fields[5] == name:
                raw = bytes.fromhex(fields[0])
                addresses.add(str(ipaddress.IPv6Address(raw)))
    return addresses


def _socket(name, family):
    """Create the socket that listens on and sends to one network.

    SO_BINDTODEVICE limits it to that interface. The packet-info option makes
    recvmsg report the destination address, which tells multicast from
    unicast. Joining the group makes the kernel deliver group traffic here.
    The multicast options choose the outgoing interface for sends.

    Args:
        name: Interface name.
        family: socket.AF_INET or socket.AF_INET6.

    Returns:
        A bound UDP socket on port 5353, ready for recvmsg and sendto.
    """
    index = interface_index(name)
    s = socket.socket(family, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, name.encode())
    if family == socket.AF_INET:
        s.bind(("", PORT))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_PKTINFO, 1)
        # ip_mreqn: group, local address (unused, so zero), interface index.
        mreqn = struct.pack("4s4si", socket.inet_aton(MDNS_V4), b"\0" * 4, index)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreqn)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, struct.pack("4s4si", b"\0" * 4, b"\0" * 4, index))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    else:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s.bind(("::", PORT))
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)
        # ipv6_mreq: group address and interface index.
        mreq = struct.pack("16sI", socket.inet_pton(socket.AF_INET6, MDNS_V6), index)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, index)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255)
    return s


def _legacy_socket(name, family):
    """Create the ephemeral socket that forwards legacy queries on one network.

    It is not bound to port 5353 and does not join the group. Responders see
    the query as a legacy query and send their reply here, unicast.

    Args:
        name: Interface name.
        family: socket.AF_INET or socket.AF_INET6.

    Returns:
        A UDP socket bound to an ephemeral port on the interface.
    """
    index = interface_index(name)
    s = socket.socket(family, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, name.encode())
    if family == socket.AF_INET:
        s.bind(("", 0))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, struct.pack("4s4si", b"\0" * 4, b"\0" * 4, index))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    else:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s.bind(("::", 0))
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, index)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255)
    return s


def _destination(ancdata, family):
    """Read a received packet's destination address from its control data.

    For IPv4 that is the header's destination field. For IPv6 it's the first
    16 bytes of the packet-info structure.

    Args:
        ancdata: Ancillary data returned by recvmsg.
        family: socket.AF_INET or socket.AF_INET6.

    Returns:
        The destination address as a string, or None if it isn't present.
    """
    for level, kind, data in ancdata:
        if family == socket.AF_INET and level == socket.IPPROTO_IP and kind == socket.IP_PKTINFO:
            return socket.inet_ntoa(data[8:12])
        if family == socket.AF_INET6 and level == socket.IPPROTO_IPV6 and kind == socket.IPV6_PKTINFO:
            return str(ipaddress.IPv6Address(data[:16]))
    return None


def log_decisions(message, networks, outputs):
    """Log one DEBUG line per output network, saying relayed or dropped.

    Args:
        message: The message that was decided.
        networks: Names of all networks the container has.
        outputs: Output networks the message was relayed to.
    """
    for output in networks:
        if output == message.source:
            continue
        result = "relayed" if output in outputs else "dropped"
        log.debug(
            "source=%s output=%s kind=%s delivery=%s result=%s",
            message.source, output, message.kind, message.delivery, result,
        )


def remember_query(pending, relay_id, original_id, source, querier, outputs, now):
    """Record a relayed QU query so a later reply can find the querier.

    Entries are keyed by (output network, relay ID). The output network is
    where the reply will come back.

    Args:
        pending: Dict of pending queries, updated in place.
        relay_id: The ID the relay put on the query.
        original_id: The querier's own two-byte query ID, restored on the reply.
        source: Network the query arrived on, where its reply must go back.
        querier: Address of the device that sent the query.
        outputs: Networks the query was relayed to.
        now: Current time from time.monotonic().
    """
    for output in outputs:
        entries = pending.setdefault((output, relay_id), [])
        entries.append(Pending(source, querier, original_id, now + QUERY_WINDOW))


def answer_targets(pending, network, payload, now, outputs):
    """Find the queriers a reply should go back to.

    Expired entries are removed. Only entries whose querier network is in
    `outputs` are returned, so a reply still needs its reverse rule to
    allow it.

    Args:
        pending: Dict of pending queries, updated in place.
        network: Network the reply arrived on.
        payload: The raw reply packet. The first two bytes are the relay ID.
        now: Current time from time.monotonic().
        outputs: Networks the reply is allowed to go to.

    Returns:
        A list of Pending entries to send the reply to.
    """
    key = (network, struct.unpack_from("!H", payload, 0)[0])
    live = [entry for entry in pending.get(key, []) if entry.expires > now]
    pending[key] = live
    return [entry for entry in live if entry.source in outputs]


def send_unicast(sockets, network, querier, payload, port=PORT):
    """Send a unicast reply to a querier on its network.

    IPv6 link-local addresses need the interface index as a scope.

    Args:
        sockets: Dict of relay sockets, keyed by (network, family).
        network: Network the querier is on.
        querier: Address of the device to send to.
        payload: The raw packet to send.
        port: The querier's port. Defaults to the mDNS port.
    """
    if ":" in querier:
        target = (querier, port, 0, interface_index(network))
        sockets[(network, socket.AF_INET6)].sendto(payload, target)
    else:
        sockets[(network, socket.AF_INET)].sendto(payload, (querier, port))


class Relay:
    """Holds the sockets and state for one relay process.

    Attributes:
        rules: Rules in file order.
        names: Names of the networks being relayed between.
        own: Every address the mirror holds, used for the loop check.
        sockets: mDNS sockets, keyed by (network, family).
        legacy_sockets: Legacy query sockets, keyed by (network, family).
        roles: Maps each socket to ("mdns" or "legacy", network, family).
        pending: Relayed QU queries waiting for replies, keyed by
            (output network, relay ID).
        slots: Relayed legacy queries waiting for replies, keyed by the ID
            the relay put on the query.
    """

    def __init__(self, rules, names):
        """Open the sockets for every network.

        Args:
            rules: Rules in file order, as returned by load_rules.
            names: Container interface names to relay between.

        Raises:
            OSError: If a socket can't be created or bound.
        """
        self.rules = rules
        self.names = names
        self.own = set()
        for name in names:
            self.own |= interface_addresses(name)
        self.sockets = {}
        self.legacy_sockets = {}
        self.roles = {}
        for name in names:
            for family in (socket.AF_INET, socket.AF_INET6):
                sock = _socket(name, family)
                self.sockets[(name, family)] = sock
                self.roles[sock] = ("mdns", name, family)
                legacy = _legacy_socket(name, family)
                self.legacy_sockets[(name, family)] = legacy
                self.roles[legacy] = ("legacy", name, family)
        self.pending = {}
        self.slots = {}

    def serve(self):
        """Relay traffic until the process stops."""
        while True:
            readable, _, _ = select.select(list(self.roles), [], [])
            for sock in readable:
                self._dispatch(sock)

    def _dispatch(self, sock):
        """Read one packet from a socket and send it to the right handler.

        Args:
            sock: The socket that has data ready.
        """
        role, name, family = self.roles[sock]
        payload, ancdata, _, source = sock.recvmsg(9000, 1024)
        if role == "legacy":
            self._legacy_reply(name, payload, source)
            return
        destination = _destination(ancdata, family)
        if destination is None:
            return
        try:
            kind, qu = classify(payload)
        except (ValueError, IndexError):
            # Too short or malformed to classify. Drop it.
            return
        group = ipaddress.ip_address(destination).is_multicast
        # The source may include an IPv6 scope suffix, such as "%eth0".
        # Remove it so the address can be compared with our own.
        sender = source[0].split("%")[0]
        if source[1] != PORT:
            self._legacy_query(name, family, payload, kind, sender, group, source[1])
        else:
            self._mdns(name, family, payload, kind, qu, sender, group)

    def _mdns(self, name, family, payload, kind, qu, sender, group):
        """Relay a message sent from port 5353.

        Args:
            name: Network the message arrived on.
            family: socket.AF_INET or socket.AF_INET6.
            payload: The raw packet.
            kind: "query" or "advertisement".
            qu: True if a query asks for a unicast reply.
            sender: Address the message came from.
            group: True if the message was sent to the multicast group.
        """
        message = Message(source=name, kind=kind, sender=sender, addressed_to_group=group, qu=qu)
        try:
            outbound = strip_link_local(payload)
        except ValueError:
            return
        outputs = decide(self.rules, message, self.names, self.own)
        log_decisions(message, self.names, outputs)
        now = time.monotonic()
        if group:
            if qu and outputs:
                relay_id = self._new_id(now)
                remember_query(self.pending, relay_id, payload[:2], name, sender, outputs, now)
                outbound = struct.pack("!H", relay_id) + outbound[2:]
            for output in outputs:
                target = (MDNS_V4, PORT) if family == socket.AF_INET else (MDNS_V6, PORT, 0, interface_index(output))
                self.sockets[(output, family)].sendto(outbound, target)
        else:
            for entry in answer_targets(self.pending, name, payload, now, outputs):
                restored = entry.original_id + outbound[2:]
                send_unicast(self.sockets, entry.source, entry.querier, restored)

    def _legacy_query(self, name, family, payload, kind, sender, group, port):
        """Relay a legacy query, sent from a port other than 5353.

        The query's ID is replaced with one the relay chose, so replies can be
        matched back to this query. Only queries with no answer or authority
        records are relayed, as Avahi does.

        Args:
            name: Network the query arrived on.
            family: socket.AF_INET or socket.AF_INET6.
            payload: The raw query packet.
            kind: The packet's kind, from classify.
            sender: Address the query came from.
            group: True if the query was sent to the multicast group.
            port: The querier's source port.
        """
        if kind != "query" or len(payload) < 12:
            return
        _, _, _, answers, authority, _ = struct.unpack_from("!HHHHHH", payload, 0)
        if answers or authority:
            return
        message = Message(source=name, kind="query", sender=sender, addressed_to_group=group)
        outputs = decide(self.rules, message, self.names, self.own)
        log_decisions(message, self.names, outputs)
        if not outputs:
            return
        now = time.monotonic()
        slot_id = self._new_id(now)
        self.slots[slot_id] = Legacy(name, sender, port, payload[:2], now + LEGACY_WINDOW)
        outbound = struct.pack("!H", slot_id) + payload[2:]
        for output in outputs:
            target = (MDNS_V4, PORT) if family == socket.AF_INET else (MDNS_V6, PORT, 0, interface_index(output))
            self.legacy_sockets[(output, family)].sendto(outbound, target)

    def _legacy_reply(self, name, payload, source):
        """Relay a unicast reply to a legacy query the relay forwarded.

        Args:
            name: Network the reply arrived on.
            payload: The raw reply packet.
            source: The responder's (address, port) as reported by recvmsg.
        """
        try:
            kind, _ = classify(payload)
        except (ValueError, IndexError):
            return
        if kind != "advertisement":
            return
        now = time.monotonic()
        slot = self.slots.get(struct.unpack_from("!H", payload, 0)[0])
        if slot is None or slot.expires <= now:
            return
        sender = source[0].split("%")[0]
        message = Message(source=name, kind="advertisement", sender=sender, addressed_to_group=False)
        outputs = decide(self.rules, message, self.names, self.own)
        log_decisions(message, self.names, outputs)
        if slot.source not in outputs:
            return
        restored = slot.original_id + payload[2:]
        try:
            outbound = strip_link_local(restored)
        except ValueError:
            return
        send_unicast(self.sockets, slot.source, slot.querier, outbound, port=slot.port)

    def _new_id(self, now):
        """Pick an ID for a new relayed query that no live query is using.

        Legacy queries and QU queries share the ID space, so both are checked.

        Args:
            now: Current time from time.monotonic(). Expired entries are removed.

        Returns:
            An ID from 1 to 65535.
        """
        self.slots = {k: v for k, v in self.slots.items() if v.expires > now}
        for key in list(self.pending):
            self.pending[key] = [e for e in self.pending[key] if e.expires > now]
            if not self.pending[key]:
                del self.pending[key]
        used = set(self.slots) | {relay_id for _, relay_id in self.pending}
        for candidate in range(1, 65536):
            if candidate not in used:
                return candidate
        raise RuntimeError("no free relay query IDs")


def run(rules, names):
    """Relay mDNS between the named networks until the process stops.

    Args:
        rules: Rules in file order, as returned by load_rules.
        names: Container interface names to relay between.

    Raises:
        OSError: If a socket can't be created or bound, for example when
            an interface doesn't exist.
    """
    Relay(rules, names).serve()
