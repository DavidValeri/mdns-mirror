import logging

import pytest

from mdns_mirror.relay import log_decisions
from mdns_mirror.rules import Message

pytestmark = pytest.mark.covers("mdns-mirror:story:28")

NETWORKS = ["personal", "iot", "nas"]


def test_each_output_gets_one_decision_line(caplog):
    message = Message("personal", "advertisement", "192.168.10.50")
    with caplog.at_level(logging.DEBUG, logger="mdns_mirror"):
        log_decisions(message, NETWORKS, {"iot"})
    lines = [r.getMessage() for r in caplog.records]
    assert lines == [
        "source=personal output=iot kind=advertisement delivery=broadcast result=relayed",
        "source=personal output=nas kind=advertisement delivery=broadcast result=dropped",
    ]


@pytest.mark.covers("mdns-mirror:story:29")
def test_decision_lines_are_debug_so_they_stay_quiet_by_default(caplog):
    message = Message("personal", "query", "192.168.10.50", addressed_to_group=False)
    with caplog.at_level(logging.INFO, logger="mdns_mirror"):
        log_decisions(message, NETWORKS, set())
    assert caplog.records == []


def test_unicast_delivery_is_logged(caplog):
    message = Message("personal", "query", "192.168.10.50", qu=True)
    with caplog.at_level(logging.DEBUG, logger="mdns_mirror"):
        log_decisions(message, NETWORKS, set())
    assert all("delivery=unicast" in r.getMessage() for r in caplog.records)
