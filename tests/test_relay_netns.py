import os
import platform
import shutil
import socket
import struct
import subprocess
import time

import pytest

from mdns_mirror.packet import classify

QUERY_PTR = (
    b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    b"\x05_http\x04_tcp\x05local\x00\x00\x0c\x00\x01"
)
QU_QUERY_PTR = QUERY_PTR[:-2] + b"\x80\x01"
ADVERTISEMENT = b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00"


@pytest.mark.covers("mdns-mirror:story:13")
def test_query_is_classified_as_query():
    assert classify(QUERY_PTR) == ("query", False)


@pytest.mark.covers("mdns-mirror:story:17")
def test_qu_bit_in_question_marks_query_as_qu():
    assert classify(QU_QUERY_PTR) == ("query", True)


@pytest.mark.covers("mdns-mirror:story:11")
def test_response_is_classified_as_advertisement():
    assert classify(ADVERTISEMENT) == ("advertisement", False)


@pytest.mark.covers("mdns-mirror:story:24")
def test_short_packet_is_rejected():
    with pytest.raises(ValueError):
        classify(b"\x00\x01")


@pytest.mark.covers("mdns-mirror:story:24")
def test_compressed_question_name_is_skipped():
    packet = (
        b"\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00"
        b"\x05_http\x04_tcp\x05local\x00\x00\x0c\x00\x01"
        b"\xc0\x0c\x00\x0c\x80\x01"
    )
    assert classify(packet) == ("query", True)


netns_only = pytest.mark.skipif(
    not platform.system() == "Linux" or os.geteuid() != 0 or shutil.which("ip") is None,
    reason="needs Linux, root, and iproute2",
)

FIREWALL = os.path.abspath("deploy/firewall.nft")


def _ip(*args):
    subprocess.run(["ip", *args], check=True)


def _in_ns(ns, *args):
    return subprocess.run(["ip", "netns", "exec", ns, *args], check=True, capture_output=True, text=True)


@pytest.fixture
def mirror_topology():
    names = ["ns-relay", "ns-a", "ns-b"]
    for ns in names:
        _ip("netns", "add", ns)
    _ip("link", "add", "a0", "type", "veth", "peer", "name", "ra")
    _ip("link", "set", "a0", "netns", "ns-a")
    _ip("link", "set", "ra", "netns", "ns-relay")
    _ip("link", "add", "b0", "type", "veth", "peer", "name", "rb")
    _ip("link", "set", "b0", "netns", "ns-b")
    _ip("link", "set", "rb", "netns", "ns-relay")
    for ns, dev, v4, v6 in (
        ("ns-a", "a0", "192.168.10.10/24", "fd00:10::10/64"),
        ("ns-relay", "ra", "192.168.10.2/24", "fd00:10::2/64"),
        ("ns-b", "b0", "192.168.20.10/24", "fd00:20::10/64"),
        ("ns-relay", "rb", "192.168.20.2/24", "fd00:20::2/64"),
    ):
        _in_ns(ns, "ip", "addr", "add", v4, "dev", dev)
        _in_ns(ns, "ip", "addr", "add", v6, "dev", dev, "nodad")
        _in_ns(ns, "ip", "link", "set", dev, "up")
    yield
    for ns in names:
        subprocess.run(["ip", "netns", "del", ns], check=False)


LISTENER_V4 = (
    "import socket,struct;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(5);print(s.recvfrom(9000)[0].hex())"
)
LISTENER_V6 = (
    "import socket;s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('::',5353));"
    "idx=socket.if_nametoindex('b0');"
    "s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_JOIN_GROUP,socket.inet_pton(socket.AF_INET6,'ff02::fb')+idx.to_bytes(4,'little'));"
    "s.settimeout(5);print(s.recvfrom(9000)[0].hex())"
)
SENDER_V4 = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    "s.sendto(bytes.fromhex('000084000000000000000000'),('224.0.0.251',5353))"
)
SENDER_V6 = (
    "import socket;s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('::',5353));"
    "s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_MULTICAST_IF,socket.if_nametoindex('a0'));"
    "s.sendto(bytes.fromhex('000084000000000000000000'),('ff02::fb',5353,0,0))"
)
CASES = {
    "v4": (LISTENER_V4, SENDER_V4),
    "v6": (LISTENER_V6, SENDER_V6),
}


def _run_relay(tmp_path, action):
    rules = tmp_path / "rules.yaml"
    rules.write_text(f"rules:\n  - action: {action}\n    source: ra\n    output: rb\n")
    return subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )


@netns_only
@pytest.mark.parametrize("family", ["v4", "v6"])
@pytest.mark.parametrize("action", ["allow", "deny"])
@pytest.mark.covers("mdns-mirror:story:11", "mdns-mirror:story:12", "mdns-mirror:story:43")
def test_advertisement_is_relayed_only_when_allowed(mirror_topology, tmp_path, family, action):
    listener_code, sender_code = CASES[family]
    relay = _run_relay(tmp_path, action)
    try:
        time.sleep(1)
        listener = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", listener_code],
            stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        _in_ns("ns-a", "python3", "-c", sender_code)
        out, _ = listener.communicate(timeout=15)
        if action == "allow":
            assert out.strip() == "000084000000000000000000"
        else:
            assert out.strip() == ""
    finally:
        relay.terminate()
        relay.wait(timeout=5)


@netns_only
@pytest.mark.covers("mdns-mirror:story:44", "adr:0002")
def test_link_local_records_are_stripped_and_global_records_kept(mirror_topology, tmp_path):
    def name(labels):
        return b"".join(bytes([len(label)]) + label for label in labels) + b"\0"

    def record(rtype, rdata):
        return name([b"_http", b"_tcp", b"local"]) + struct.pack("!HHIH", rtype, 0x8001, 120, len(rdata)) + rdata

    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 2, 0, 0)
    link_local = record(28, socket.inet_pton(socket.AF_INET6, "fe80::1"))
    global_record = record(28, socket.inet_pton(socket.AF_INET6, "2001:db8::1"))
    sent = header + link_local + global_record
    expected = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0) + global_record
    sender_code = (
        "import socket;s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM);"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('::',5353));"
        "s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_MULTICAST_IF,socket.if_nametoindex('a0'));"
        f"s.sendto(bytes.fromhex('{sent.hex()}'),('ff02::fb',5353,0,0))"
    )
    relay = _run_relay(tmp_path, "allow")
    try:
        time.sleep(1)
        listener = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", LISTENER_V6],
            stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        _in_ns("ns-a", "python3", "-c", sender_code)
        out, _ = listener.communicate(timeout=15)
        assert out.strip() == expected.hex()
    finally:
        relay.terminate()
        relay.wait(timeout=5)


@netns_only
@pytest.mark.covers("mdns-mirror:story:45")
def test_relayed_packets_keep_source_port_5353(mirror_topology, tmp_path):
    listener_code = (
        "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
        "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
        "s.settimeout(5);print(s.recvfrom(9000)[1][1])"
    )
    relay = _run_relay(tmp_path, "allow")
    try:
        time.sleep(1)
        listener = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", listener_code],
            stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        _in_ns("ns-a", "python3", "-c", SENDER_V4)
        out, _ = listener.communicate(timeout=15)
        assert out.strip() == "5353"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


UNICAST_LISTENER = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.bind(('',9999));s.settimeout(5);print(s.recvfrom(9000)[0].hex())"
)
UNICAST_SENDER = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.sendto(b'hello',('192.168.20.10',9999))"
)


def _route_through_relay():
    _in_ns("ns-a", "ip", "route", "add", "192.168.20.0/24", "via", "192.168.10.2")
    _in_ns("ns-b", "ip", "route", "add", "192.168.10.0/24", "via", "192.168.20.2")
    _in_ns("ns-relay", "sh", "-c", "echo 1 > /proc/sys/net/ipv4/ip_forward")


@netns_only
@pytest.mark.parametrize("lockdown", [False, True])
@pytest.mark.covers("mdns-mirror:story:24", "mdns-mirror:story:25", "adr:0001")
def test_non_mdns_traffic_is_forwarded_only_without_lockdown(mirror_topology, lockdown):
    _route_through_relay()
    if lockdown:
        _in_ns("ns-relay", "nft", "-f", FIREWALL)
    listener = subprocess.Popen(
        ["ip", "netns", "exec", "ns-b", "python3", "-c", UNICAST_LISTENER],
        stdout=subprocess.PIPE, text=True,
    )
    time.sleep(1)
    _in_ns("ns-a", "python3", "-c", UNICAST_SENDER)
    out, _ = listener.communicate(timeout=15)
    if lockdown:
        assert out.strip() == ""
    else:
        assert out.strip() == b"hello".hex()


@netns_only
@pytest.mark.covers("mdns-mirror:story:25")
def test_advertisement_is_still_relayed_under_lockdown(mirror_topology, tmp_path):
    _in_ns("ns-relay", "nft", "-f", FIREWALL)
    listener_code, sender_code = CASES["v4"]
    relay = _run_relay(tmp_path, "allow")
    try:
        time.sleep(1)
        listener = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", listener_code],
            stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        _in_ns("ns-a", "python3", "-c", sender_code)
        out, _ = listener.communicate(timeout=15)
        assert out.strip() == "000084000000000000000000"
    finally:
        relay.terminate()
        relay.wait(timeout=5)
