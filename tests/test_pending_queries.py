import pytest

from mdns_mirror.relay import QUERY_WINDOW, answer_targets, remember_query

QUERY_ID = b"\x12\x34"
RELAY_ID = 4242
PAYLOAD = QUERY_ID + b"\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"


@pytest.mark.covers("adr:0004")
def test_reply_is_sent_to_the_querier_within_the_window():
    pending = {}
    remember_query(pending, RELAY_ID, QUERY_ID, "personal", "192.168.10.50", {"iot"}, now=100.0)
    reply = RELAY_ID.to_bytes(2, "big") + b"\x84\x00" + b"\x00" * 8
    targets = answer_targets(pending, "iot", reply, now=101.0, outputs={"personal"})
    assert [(t.source, t.querier, t.original_id) for t in targets] == [("personal", "192.168.10.50", QUERY_ID)]


@pytest.mark.covers("adr:0004")
def test_reply_after_the_window_is_not_sent():
    pending = {}
    remember_query(pending, RELAY_ID, QUERY_ID, "personal", "192.168.10.50", {"iot"}, now=100.0)
    reply = RELAY_ID.to_bytes(2, "big") + b"\x84\x00" + b"\x00" * 8
    targets = answer_targets(pending, "iot", reply, now=100.0 + QUERY_WINDOW + 1, outputs={"personal"})
    assert targets == []


@pytest.mark.covers("adr:0004")
def test_reply_for_a_different_relay_id_is_not_sent():
    pending = {}
    remember_query(pending, RELAY_ID, QUERY_ID, "personal", "192.168.10.50", {"iot"}, now=100.0)
    other = (RELAY_ID + 1).to_bytes(2, "big") + b"\x84\x00" + b"\x00" * 8
    assert answer_targets(pending, "iot", other, now=101.0, outputs={"personal"}) == []


@pytest.mark.covers("adr:0004", "story:17")
def test_reply_is_not_sent_when_its_rule_denies_the_output():
    pending = {}
    remember_query(pending, RELAY_ID, QUERY_ID, "personal", "192.168.10.50", {"iot"}, now=100.0)
    reply = RELAY_ID.to_bytes(2, "big") + b"\x84\x00" + b"\x00" * 8
    assert answer_targets(pending, "iot", reply, now=101.0, outputs=set()) == []
