import sys

import pytest

from mdns_mirror import __main__ as entry
from mdns_mirror.rules import check_networks, load_rules


@pytest.mark.covers("story:26")
def test_invalid_yaml_is_rejected():
    with pytest.raises(ValueError, match="not valid YAML"):
        load_rules("rules: [unclosed")


@pytest.mark.covers("story:26")
def test_rule_missing_a_field_is_rejected():
    with pytest.raises(ValueError, match="missing a required field"):
        load_rules("rules:\n  - action: allow\n    source: personal\n")


@pytest.mark.covers("story:27")
def test_rule_naming_unknown_network_is_rejected():
    rules = load_rules("rules:\n  - action: allow\n    source: personal\n    output: garage\n")
    with pytest.raises(ValueError, match="garage"):
        check_networks(rules, ["personal", "iot"])


@pytest.mark.covers("story:8")
def test_rules_naming_only_known_networks_pass():
    rules = load_rules("rules:\n  - action: allow\n    source: personal\n    output: iot\n")
    check_networks(rules, ["personal", "iot"])


@pytest.mark.covers("story:7", "story:26")
def test_startup_stops_on_bad_rule_file_before_relaying(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules: [unclosed")
    relayed = []
    monkeypatch.setattr(entry, "run", lambda *a: relayed.append(a))
    with pytest.raises(SystemExit) as exit_info:
        entry.main(["--rules", str(rules), "personal", "iot"])
    assert exit_info.value.code == 1
    assert relayed == []


@pytest.mark.covers("story:27")
def test_startup_stops_on_unknown_network_before_relaying(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - action: allow\n    source: personal\n    output: garage\n")
    relayed = []
    monkeypatch.setattr(entry, "run", lambda *a: relayed.append(a))
    with pytest.raises(SystemExit) as exit_info:
        entry.main(["--rules", str(rules), "personal", "iot"])
    assert exit_info.value.code == 1
    assert relayed == []


@pytest.mark.covers("story:27")
def test_startup_names_interfaces_that_are_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules: []\n")
    relayed = []
    monkeypatch.setattr(entry, "run", lambda *a: relayed.append(a))
    with pytest.raises(SystemExit) as exit_info:
        entry.main(["--rules", str(rules), "mdns-absent-0", "mdns-absent-1"])
    assert exit_info.value.code == 1
    assert "mdns-absent-0, mdns-absent-1" in capsys.readouterr().err
    assert relayed == []
