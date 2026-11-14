# mDNS Mirror

A service that selectively relays mDNS traffic between the LANs it is attached to, under allow and deny rules, so that devices on one LAN can discover services on another.

## Networks

**Network**:
A LAN or VLAN the mirror is attached to. Each network is a separate segment with its own addresses.
_Avoid_: Subnet, segment, interface

**Source network**:
The network a mDNS message arrives on. Rules match on it.
_Avoid_: Ingress, input network

**Output network**:
The network a mirrored mDNS message is sent to. Rules match on it.
_Avoid_: Egress, destination network

**Management network**:
The network that carries SSH access to the mirror VM. It is mirrored like any other network.
_Avoid_: Admin network, out-of-band network

## Traffic

**Mirror**:
To relay an mDNS message from a source network to an output network. Only mirrored messages cross between networks.
_Avoid_: Route, forward, bridge

**Advertisement**:
An mDNS message that announces a service or record.
_Avoid_: Announcement, broadcast record

**Query**:
An mDNS message that asks for a service or record.
_Avoid_: Lookup, request

**Relay ID**:
The query ID the mirror puts on a query it relays, so that a reply can be matched back to that query.
_Avoid_: Transaction ID, mapped ID

**Broadcast**:
mDNS traffic delivered to the multicast group.
_Avoid_: Multicast (in rules), IP broadcast

**Unicast**:
mDNS traffic delivered to a single address, such as a unicast reply or a QU query.
_Avoid_: Point-to-point

**Legacy unicast query**:
A query sent from a port other than 5353, which expects a unicast reply to that port. Distinct from a QU query.
_Avoid_: Unicast query, port 53 query

## Addresses

**Link-local record**:
An A or AAAA record whose address is valid only on the network it came from. The mirror does not relay these.
_Avoid_: Local address record, self-assigned address

## Rules

**Rule**:
An ordered entry that allows or denies mirroring of a given message kind and delivery type from one source network to one output network.
_Avoid_: Filter, policy entry

**Default-deny**:
A message that matches no rule is not mirrored.
_Avoid_: Default-allow, fallback

**Reflection loop**:
A mirrored message that re-enters a network the mirror is watching and gets mirrored again, endlessly.
_Avoid_: Echo, storm

## Releases

**Release tag**:
A SemVer git tag (`vX.Y.Z`) on a commit reachable from `main`. Pushing one starts a Release.
_Avoid_: Version tag on a branch, build tag

**Release**:
The GitHub Release created from a Release tag, with the built artifacts and generated notes.
_Avoid_: Build, publish
