import pytest

from mdns_mirror.rules import Message, decide, load_rules

pytestmark = pytest.mark.covers("mdns-mirror:story:38")

NETWORKS = ["personal", "iot", "nas"]
PEER = "192.168.10.50"
MIRROR = "192.168.20.2"


def msg(source="personal", kind="advertisement", addressed_to_group=True, qu=False, sender=PEER):
    return Message(source, kind, sender, addressed_to_group, qu)


def rules_from(body):
    return load_rules("rules:\n" + body)


@pytest.mark.covers("mdns-mirror:story:10", "mdns-mirror:story:37")
def test_no_rules_denies_everything():
    assert decide([], msg(), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:11")
def test_allow_rule_sends_to_output_network():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n")
    assert decide(rules, msg(), NETWORKS) == {"iot"}


@pytest.mark.covers("mdns-mirror:story:12")
def test_deny_rule_blocks_output_network():
    rules = rules_from("  - action: deny\n    source: personal\n    output: iot\n")
    assert decide(rules, msg(), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:9")
def test_first_matching_rule_wins():
    rules = rules_from(
        "  - action: deny\n    source: personal\n    output: iot\n"
        "  - action: allow\n    source: personal\n    output: iot\n"
    )
    assert decide(rules, msg(), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:21")
def test_message_is_never_sent_back_to_its_source():
    rules = rules_from("  - action: allow\n    source: personal\n    output: personal\n")
    assert decide(rules, msg(), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:20")
def test_rules_for_other_sources_do_not_apply():
    rules = rules_from("  - action: allow\n    source: iot\n    output: nas\n")
    assert decide(rules, msg(), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:19")
def test_one_source_can_fan_out_to_several_outputs():
    rules = rules_from(
        "  - action: allow\n    source: personal\n    output: iot\n"
        "  - action: allow\n    source: personal\n    output: nas\n"
    )
    assert decide(rules, msg(), NETWORKS) == {"iot", "nas"}


@pytest.mark.covers("mdns-mirror:story:26")
def test_unknown_action_is_rejected():
    try:
        rules_from("  - action: maybe\n    source: personal\n    output: iot\n")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


@pytest.mark.covers("mdns-mirror:story:11", "mdns-mirror:story:14")
def test_advertisement_rule_does_not_allow_queries():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n    kind: advertisement\n")
    assert decide(rules, msg(kind="query"), NETWORKS) == set()
    assert decide(rules, msg(kind="advertisement"), NETWORKS) == {"iot"}


@pytest.mark.covers("mdns-mirror:story:13")
def test_query_rule_does_not_allow_advertisements():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n    kind: query\n")
    assert decide(rules, msg(kind="advertisement"), NETWORKS) == set()
    assert decide(rules, msg(kind="query"), NETWORKS) == {"iot"}


@pytest.mark.covers("mdns-mirror:story:15")
def test_broadcast_rule_does_not_allow_unicast():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n    delivery: broadcast\n")
    assert decide(rules, msg(addressed_to_group=True), NETWORKS) == {"iot"}
    assert decide(rules, msg(addressed_to_group=False), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:16")
def test_unicast_rule_does_not_allow_broadcast():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n    delivery: unicast\n")
    assert decide(rules, msg(addressed_to_group=False), NETWORKS) == {"iot"}
    assert decide(rules, msg(addressed_to_group=True), NETWORKS) == set()


@pytest.mark.covers("mdns-mirror:story:17")
def test_qu_query_is_treated_as_unicast():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n    delivery: unicast\n")
    assert decide(rules, msg(kind="query", qu=True), NETWORKS) == {"iot"}


@pytest.mark.covers("mdns-mirror:story:22")
def test_message_from_mirror_own_address_is_never_mirrored():
    rules = rules_from("  - action: allow\n    source: personal\n    output: iot\n")
    assert decide(rules, msg(sender=MIRROR), NETWORKS, own_addresses={MIRROR}) == set()


@pytest.mark.covers("mdns-mirror:story:26")
def test_unknown_kind_or_delivery_is_rejected():
    for bad in ("  - action: allow\n    source: personal\n    output: iot\n    kind: announce\n",
                "  - action: allow\n    source: personal\n    output: iot\n    delivery: anycast\n"):
        try:
            rules_from(bad)
        except ValueError:
            continue
        raise AssertionError("expected ValueError")
