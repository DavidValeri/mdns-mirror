import socket
import struct

import pytest

from mdns_mirror.packet import TYPE_A, TYPE_AAAA, TYPE_PTR, classify, strip_link_local

pytestmark = pytest.mark.covers("story:44", "adr:0002")

SERVICE = [b"_http", b"_tcp", b"local"]
GLOBAL_V6 = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
LINK_LOCAL_V6 = socket.inet_pton(socket.AF_INET6, "fe80::1")
LINK_LOCAL_V4 = socket.inet_aton("169.254.7.7")
GLOBAL_V4 = socket.inet_aton("192.168.10.7")


def _name(labels):
    return b"".join(bytes([len(label)]) + label for label in labels) + b"\0"


def _record(labels, rtype, rdata, rclass=0x8001, ttl=120):
    return _name(labels) + struct.pack("!HHIH", rtype, rclass, ttl, len(rdata)) + rdata


def _packet(answers=(), additional=(), questions=(), flags=0x8400, packet_id=0):
    header = struct.pack("!HHHHHH", packet_id, flags, len(questions), len(answers), 0, len(additional))
    return header + b"".join(questions) + b"".join(answers) + b"".join(additional)


def test_packet_without_link_local_records_is_returned_unchanged():
    packet = _packet(answers=[_record(SERVICE, TYPE_AAAA, GLOBAL_V6)])
    assert strip_link_local(packet) is packet


def test_link_local_aaaa_record_is_removed_and_count_updated():
    keep = _record(SERVICE, TYPE_AAAA, GLOBAL_V6)
    drop = _record(SERVICE, TYPE_AAAA, LINK_LOCAL_V6)
    result = strip_link_local(_packet(answers=[drop, keep]))
    assert result == _packet(answers=[keep])
    assert struct.unpack_from("!H", result, 6)[0] == 1


def test_link_local_a_record_is_removed_from_additional_section():
    keep = _record(SERVICE, TYPE_A, GLOBAL_V4)
    drop = _record(SERVICE, TYPE_A, LINK_LOCAL_V4)
    result = strip_link_local(_packet(answers=[keep], additional=[drop]))
    assert result == _packet(answers=[keep], additional=[])


def test_compressed_name_in_rdata_is_rewritten_uncompressed():
    question = _name(SERVICE) + struct.pack("!HH", TYPE_PTR, 1)
    # The pointer 0xc00c points at offset 12, where the question name starts.
    ptr_rdata = b"\x07printer" + b"\xc0\x0c"
    compressed = _record(SERVICE, TYPE_PTR, ptr_rdata)
    drop = _record(SERVICE, TYPE_AAAA, LINK_LOCAL_V6)
    packet = _packet(questions=[question], answers=[drop, compressed])
    result = strip_link_local(packet)
    expected_rdata = _name([b"printer"] + SERVICE)
    expected = _packet(questions=[question], answers=[_record(SERVICE, TYPE_PTR, expected_rdata)])
    assert result == expected
    assert classify(result) == ("advertisement", False)


def test_truncated_packet_raises_value_error():
    packet = _packet(answers=[_record(SERVICE, TYPE_AAAA, LINK_LOCAL_V6)])
    with pytest.raises(ValueError):
        strip_link_local(packet[:-5])


def test_short_packet_raises_value_error():
    with pytest.raises(ValueError):
        strip_link_local(b"\x00\x01")
