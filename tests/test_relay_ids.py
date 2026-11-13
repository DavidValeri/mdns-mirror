import pytest

from mdns_mirror.relay import Legacy, Pending, Relay

pytestmark = pytest.mark.covers("adr:0004")


def _relay():
    relay = object.__new__(Relay)
    relay.slots = {}
    relay.pending = {}
    return relay


def test_first_id_is_one():
    relay = _relay()
    assert relay._new_id(now=100.0) == 1


def test_id_zero_is_never_returned():
    relay = _relay()
    relay.slots = {i: Legacy("ra", "192.168.10.50", 5353, b"\x00\x00", 200.0) for i in range(1, 65535)}
    assert relay._new_id(now=100.0) == 65535


def test_id_in_use_by_a_live_legacy_slot_is_skipped():
    relay = _relay()
    relay.slots = {1: Legacy("ra", "192.168.10.50", 5353, b"\x00\x00", 200.0)}
    assert relay._new_id(now=100.0) == 2


def test_id_in_use_by_a_live_qu_query_is_skipped():
    relay = _relay()
    relay.pending = {("rb", 1): [Pending("ra", "192.168.10.50", b"\x12\x34", 200.0)]}
    assert relay._new_id(now=100.0) == 2


def test_expired_entries_free_their_ids():
    relay = _relay()
    relay.slots = {1: Legacy("ra", "192.168.10.50", 5353, b"\x00\x00", 50.0)}
    relay.pending = {("rb", 2): [Pending("ra", "192.168.10.50", b"\x12\x34", 50.0)]}
    assert relay._new_id(now=100.0) == 1
    assert relay.slots == {}
    assert relay.pending == {}


def test_exhausted_id_space_raises():
    relay = _relay()
    relay.slots = {i: Legacy("ra", "192.168.10.50", 5353, b"\x00\x00", 200.0) for i in range(1, 65536)}
    with pytest.raises(RuntimeError, match="no free relay query IDs"):
        relay._new_id(now=100.0)
