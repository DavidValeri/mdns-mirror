import os
import platform
import shutil
import socket
import struct
import subprocess
import time

import pytest

netns_only = pytest.mark.skipif(
    not platform.system() == "Linux" or os.geteuid() != 0 or shutil.which("ip") is None,
    reason="needs Linux, root, and iproute2",
)

FIREWALL = os.path.abspath("deploy/firewall.nft")
NETNS = ["ns-relay", "ns-a", "ns-b", "ns-c"]
ADVERTISEMENT = bytes.fromhex("000084000000000000000000")
QUERY = (
    b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    b"\x05_http\x04_tcp\x05local\x00\x00\x0c\x00\x01"
)


def _ip(*args):
    subprocess.run(["ip", *args], check=True)


def _in_ns(ns, *args):
    return subprocess.run(["ip", "netns", "exec", ns, *args], check=True, capture_output=True, text=True)


@pytest.fixture
def three_networks():
    for ns in NETNS:
        _ip("netns", "add", ns)
    links = [("a0", "ra", "ns-a", "ns-relay"), ("b0", "rb", "ns-b", "ns-relay"), ("c0", "rc", "ns-c", "ns-relay")]
    for host_dev, relay_dev, host_ns, _ in links:
        _ip("link", "add", host_dev, "type", "veth", "peer", "name", relay_dev)
        _ip("link", "set", host_dev, "netns", host_ns)
        _ip("link", "set", relay_dev, "netns", "ns-relay")
    for ns, dev, v4, v6 in (
        ("ns-a", "a0", "192.168.10.10/24", "fd00:10::10/64"),
        ("ns-relay", "ra", "192.168.10.2/24", "fd00:10::2/64"),
        ("ns-b", "b0", "192.168.20.10/24", "fd00:20::10/64"),
        ("ns-relay", "rb", "192.168.20.2/24", "fd00:20::2/64"),
        ("ns-c", "c0", "192.168.30.10/24", "fd00:30::10/64"),
        ("ns-relay", "rc", "192.168.30.2/24", "fd00:30::2/64"),
    ):
        _in_ns(ns, "ip", "addr", "add", v4, "dev", dev)
        _in_ns(ns, "ip", "addr", "add", v6, "dev", dev, "nodad")
        _in_ns(ns, "ip", "link", "set", dev, "up")
    yield
    for ns in NETNS:
        subprocess.run(["ip", "netns", "del", ns], check=False)


def _listener(ns, addr):
    code = (
        "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
        f"s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('{addr}'));"
        "s.settimeout(5);print(s.recvfrom(9000)[0].hex())"
    )
    return subprocess.Popen(["ip", "netns", "exec", ns, "python3", "-c", code], stdout=subprocess.PIPE, text=True)


def _send_multicast(ns, src, payload):
    code = (
        "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
        f"s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('{src}'));"
        f"s.sendto(bytes.fromhex('{payload.hex()}'),('224.0.0.251',5353))"
    )
    _in_ns(ns, "python3", "-c", code)


@netns_only
@pytest.mark.parametrize("payload", [ADVERTISEMENT, QUERY], ids=["advertisement", "query"])
@pytest.mark.covers("story:18", "story:39", "story:40")
def test_message_reaches_only_the_allowed_network(three_networks, tmp_path, payload):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n"
        "  - action: allow\n    source: ra\n    output: rb\n"
        "  - action: deny\n    source: ra\n    output: rc\n"
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb", "rc"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        allowed = _listener("ns-b", "192.168.20.10")
        denied = _listener("ns-c", "192.168.30.10")
        time.sleep(1)
        _send_multicast("ns-a", "192.168.10.10", payload)
        allowed_out, _ = allowed.communicate(timeout=15)
        denied_out, _ = denied.communicate(timeout=15)
        assert allowed_out.strip() == payload.hex()
        assert denied_out.strip() == ""
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def _route_through_relay():
    _in_ns("ns-a", "ip", "route", "add", "192.168.20.0/24", "via", "192.168.10.2")
    _in_ns("ns-b", "ip", "route", "add", "192.168.10.0/24", "via", "192.168.20.2")
    _in_ns("ns-relay", "sh", "-c", "echo 1 > /proc/sys/net/ipv4/ip_forward")


TCP_CONNECT = (
    "import socket;s=socket.socket();s.settimeout(5)\n"
    "try:\n s.connect(('192.168.20.10',22));print('connected')\n"
    "except OSError:\n print('blocked')"
)
TCP_LISTEN = (
    "import socket;s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
    "s.bind(('',22));s.listen();s.settimeout(8);"
    "c,_=s.accept();c.close()"
)


@netns_only
@pytest.mark.parametrize("lockdown", [False, True])
@pytest.mark.covers("story:23", "story:41", "adr:0001")
def test_unicast_tcp_is_not_mirrored_under_lockdown(three_networks, lockdown):
    _route_through_relay()
    if lockdown:
        _in_ns("ns-relay", "nft", "-f", FIREWALL)
    listener = subprocess.Popen(["ip", "netns", "exec", "ns-b", "python3", "-c", TCP_LISTEN])
    time.sleep(1)
    out = _in_ns("ns-a", "python3", "-c", TCP_CONNECT).stdout.strip()
    listener.wait(timeout=15)
    assert out == ("blocked" if lockdown else "connected")


QU_QUERY = QUERY[:-2] + b"\x80\x01"
RESPONDER = (
    "import socket,struct;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(8);d,a=s.recvfrom(9000);"
    "s.sendto(d[:2]+b'\\x84\\x00'+b'\\x00'*8,(a[0],a[1]))"
)
QU_QUERIER = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    f"s.sendto(bytes.fromhex('{QU_QUERY.hex()}'),('224.0.0.251',5353));"
    "s.settimeout(6)\n"
    "try:\n print(s.recvfrom(9000)[0].hex())\n"
    "except OSError:\n print('')"
)


@netns_only
@pytest.mark.parametrize("reply_allowed", [True, False])
@pytest.mark.covers("story:16", "story:17", "adr:0004")
def test_qu_query_gets_its_unicast_reply_back_to_the_querier(three_networks, tmp_path, reply_allowed):
    rules = tmp_path / "rules.yaml"
    reverse = "  - action: allow\n    source: rb\n    output: ra\n" if reply_allowed else ""
    rules.write_text("rules:\n  - action: allow\n    source: ra\n    output: rb\n" + reverse)
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        responder = subprocess.Popen(["ip", "netns", "exec", "ns-b", "python3", "-c", RESPONDER])
        time.sleep(1)
        out = _in_ns("ns-a", "python3", "-c", QU_QUERIER).stdout
        responder.wait(timeout=15)
        expected = (b"\x00\x00" + b"\x84\x00" + b"\x00" * 8).hex()
        assert out.strip() == (expected if reply_allowed else "")
    finally:
        relay.terminate()
        relay.wait(timeout=5)



QU_QUERY_WITH_ID = b"\x12\x34" + QU_QUERY[2:]
RESPONDER_PRINTING_ID = (
    "import socket,sys;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(8);d,a=s.recvfrom(9000);"
    "print(d[:2].hex(),flush=True);"
    "s.sendto(d[:2]+b'\\x84\\x00'+b'\\x00'*8,(a[0],a[1]))"
)
QU_QUERIER_WITH_ID = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    f"s.sendto(bytes.fromhex('{QU_QUERY_WITH_ID.hex()}'),('224.0.0.251',5353));"
    "s.settimeout(6)\n"
    "try:\n print(s.recvfrom(9000)[0].hex())\n"
    "except OSError:\n print('')"
)


@netns_only
@pytest.mark.covers("story:17", "adr:0004")
def test_qu_query_reply_is_restored_to_the_querier_id_and_relayed_with_another(three_networks, tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n  - action: allow\n    source: ra\n    output: rb\n  - action: allow\n    source: rb\n    output: ra\n"
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        responder = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", RESPONDER_PRINTING_ID], stdout=subprocess.PIPE, text=True
        )
        time.sleep(1)
        out = _in_ns("ns-a", "python3", "-c", QU_QUERIER_WITH_ID).stdout
        seen_by_responder = responder.communicate(timeout=15)[0].strip()
        assert out.strip() == (b"\x12\x34" + b"\x84\x00" + b"\x00" * 8).hex()
        assert seen_by_responder != "1234"
        assert seen_by_responder != "0000"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


LOOP_COUNTER = (
    "import socket,time;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(1);count=0;end=time.time()+4\n"
    "while time.time()<end:\n"
    " try:\n  s.recvfrom(9000);count+=1\n"
    " except OSError:\n  pass\n"
    "print(count)"
)


@netns_only
@pytest.mark.covers("story:21", "story:22", "story:42")
def test_mirrored_message_is_not_mirrored_back_in_a_loop(three_networks, tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n"
        "  - action: allow\n    source: ra\n    output: rb\n"
        "  - action: allow\n    source: rb\n    output: ra\n"
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        counter = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", LOOP_COUNTER],
            stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        _send_multicast("ns-a", "192.168.10.10", ADVERTISEMENT)
        out, _ = counter.communicate(timeout=20)
        assert out.strip() == "1"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


LEGACY_NAME = b"\x08mirror-b\x05local\x00"
LEGACY_QUERY = b"\x42\x42\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00" + LEGACY_NAME + b"\x00\x01\x00\x01"
LEGACY_RESPONDER = (
    "import socket,struct;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(8);d,a=s.recvfrom(9000);"
    "s.sendto(d[:2]+b'\\x84\\x00'+b'\\x00'*8,a)"
)
LEGACY_QUERIER = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    f"s.sendto(bytes.fromhex('{LEGACY_QUERY.hex()}'),('224.0.0.251',5353));"
    "s.settimeout(6)\n"
    "try:\n print(s.recvfrom(9000)[0].hex())\n"
    "except OSError:\n print('none')"
)


@netns_only
@pytest.mark.parametrize("reply_allowed", [True, False])
@pytest.mark.covers("story:46", "story:47", "story:48", "adr:0003")
def test_legacy_query_gets_its_reply_back_with_the_original_id(three_networks, tmp_path, reply_allowed):
    reverse = "  - action: allow\n    source: rb\n    output: ra\n" if reply_allowed else ""
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - action: allow\n    source: ra\n    output: rb\n" + reverse)
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        responder = subprocess.Popen(["ip", "netns", "exec", "ns-b", "python3", "-c", LEGACY_RESPONDER])
        time.sleep(1)
        querier = subprocess.Popen(
            ["ip", "netns", "exec", "ns-a", "python3", "-c", LEGACY_QUERIER],
            stdout=subprocess.PIPE, text=True,
        )
        out, _ = querier.communicate(timeout=20)
        responder.wait(timeout=15)
        if reply_allowed:
            assert out.strip().startswith("4242")
        else:
            assert out.strip() == "none"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


LEGACY_QUERY_WITH_ANSWER = LEGACY_QUERY[:6] + b"\x00\x01" + LEGACY_QUERY[8:]
LEGACY_QUERIER_WITH_ANSWER = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    f"s.sendto(bytes.fromhex('{LEGACY_QUERY_WITH_ANSWER.hex()}'),('224.0.0.251',5353));"
)
LEGACY_RESPONDER_REPORTING = (
    "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.20.10'));"
    "s.settimeout(6)\n"
    "try:\n d,a=s.recvfrom(9000)\n print(d[:2].hex(),flush=True)\n"
    " s.sendto(d[:2]+b'\\x84\\x00'+b'\\x00'*8,a)\n"
    "except OSError:\n print('none')"
)


@netns_only
@pytest.mark.covers("story:46", "adr:0003")
def test_legacy_reply_after_the_two_second_window_is_not_sent(three_networks, tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - action: allow\n    source: ra\n    output: rb\n  - action: allow\n    source: rb\n    output: ra\n")
    slow_responder = LEGACY_RESPONDER.replace("import socket,struct;", "import socket,struct,time;").replace(
        "s.sendto(", "time.sleep(3);s.sendto("
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        responder = subprocess.Popen(["ip", "netns", "exec", "ns-b", "python3", "-c", slow_responder])
        time.sleep(1)
        out = _in_ns("ns-a", "python3", "-c", LEGACY_QUERIER).stdout
        responder.wait(timeout=15)
        assert out.strip() == "none"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


@netns_only
@pytest.mark.covers("story:47", "adr:0003")
def test_legacy_query_with_answer_records_is_not_relayed(three_networks, tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - action: allow\n    source: ra\n    output: rb\n")
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        responder = subprocess.Popen(
            ["ip", "netns", "exec", "ns-b", "python3", "-c", LEGACY_RESPONDER_REPORTING], stdout=subprocess.PIPE, text=True
        )
        time.sleep(1)
        _in_ns("ns-a", "python3", "-c", LEGACY_QUERIER_WITH_ANSWER)
        out, _ = responder.communicate(timeout=15)
        assert out.strip() == "none"
    finally:
        relay.terminate()
        relay.wait(timeout=5)


AVAHI_CONF = """[server]
host-name=mirror-b
use-ipv4=yes
use-ipv6=yes
allow-interfaces=b0
enable-dbus=no

[wide-area]
enable-wide-area=no

[publish]
publish-hinfo=no
publish-workstation=no

[reflector]
enable-reflector=no
"""
AVAHI_QUERY_ID = 0x4242
AVAHI_MULTICAST_QUERY = (
    "import socket,struct,time;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('',5353));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton('224.0.0.251')+socket.inet_aton('192.168.10.10'));"
    "s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton('192.168.10.10'));"
    f"s.sendto(struct.pack('!HHHHHH',0,0,1,0,0,0)+bytes.fromhex('086d6972726f722d62056c6f63616c00')+struct.pack('!HH',1,1),('224.0.0.251',5353));"
    "s.settimeout(1);end=time.time()+6\n"
    "while time.time()<end:\n"
    " try:\n  print(s.recvfrom(9000)[0].hex())\n"
    " except OSError:\n  pass"
)


@pytest.fixture
def avahi_responder(three_networks, tmp_path):
    if shutil.which("avahi-daemon") is None:
        pytest.skip("avahi-daemon is not installed")
    conf = tmp_path / "avahi.conf"
    conf.write_text(AVAHI_CONF)
    os.makedirs("/run/avahi-daemon", exist_ok=True)
    proc = subprocess.Popen(
        ["ip", "netns", "exec", "ns-b", "avahi-daemon", "--no-drop-root", "--no-chroot", "--no-rlimits", "-f", str(conf)],
    )
    time.sleep(8)
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


@netns_only
@pytest.mark.covers("story:44", "story:49", "adr:0002")
def test_avahi_multicast_answer_is_relayed_without_link_local_records(three_networks, tmp_path, avahi_responder):
    from mdns_mirror.packet import strip_link_local

    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n"
        "  - action: allow\n    source: ra\n    output: rb\n"
        "  - action: allow\n    source: rb\n    output: ra\n"
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        out = _in_ns("ns-a", "python3", "-c", AVAHI_MULTICAST_QUERY).stdout
        responses = [bytes.fromhex(line) for line in out.split() if line[4:8] == "8400"]
        assert any(socket.inet_aton("192.168.20.10") in packet for packet in responses)
        for packet in responses:
            assert strip_link_local(packet) == packet
    finally:
        relay.terminate()
        relay.wait(timeout=5)


@netns_only
@pytest.mark.covers("story:48", "story:49", "adr:0003")
def test_avahi_legacy_answer_comes_back_with_the_original_id(three_networks, tmp_path, avahi_responder):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n"
        "  - action: allow\n    source: ra\n    output: rb\n"
        "  - action: allow\n    source: rb\n    output: ra\n"
    )
    relay = subprocess.Popen(
        ["ip", "netns", "exec", "ns-relay", "python3", "-m", "mdns_mirror", "--rules", str(rules), "ra", "rb"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("src")},
    )
    try:
        time.sleep(1)
        out = _in_ns("ns-a", "python3", "-c", LEGACY_QUERIER).stdout
        assert out.strip().startswith("4242")
        assert socket.inet_aton("192.168.20.10").hex() in out
    finally:
        relay.terminate()
        relay.wait(timeout=5)
