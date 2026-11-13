"""Rule model and mirror decisions.

A rule says whether messages from one network may be mirrored to another.
Rules are checked in file order and the first rule that applies decides,
so the file reads top to bottom. A message that matches no rule is denied.
"""

from dataclasses import dataclass

import yaml

ACTIONS = {"allow", "deny"}
KINDS = {"advertisement", "query", "any"}
DELIVERIES = {"broadcast", "unicast", "any"}


@dataclass(frozen=True)
class Rule:
    """One allow or deny entry from the rule file.

    `kind` and `delivery` default to "any", which matches every message of
    that type. A rule only applies to messages whose source and output
    network both match.

    Attributes:
        action: "allow" or "deny".
        source: Name of the network messages come from.
        output: Name of the network messages would be sent to.
        kind: "advertisement", "query", or "any".
        delivery: "broadcast", "unicast", or "any".
    """

    action: str
    source: str
    output: str
    kind: str = "any"
    delivery: str = "any"


@dataclass(frozen=True)
class Message:
    """An mDNS message as seen on one network.

    `sender` is the address the message came from and is used for the loop
    check. `addressed_to_group` is True when the message went to the mDNS
    multicast group. `qu` is the QU bit from a query's question, which asks
    for a unicast reply.

    Attributes:
        source: Name of the network the message arrived on.
        kind: "advertisement" or "query".
        sender: Address the message came from, without any IPv6 scope.
        addressed_to_group: True if sent to the mDNS multicast group.
        qu: True if a query asks for a unicast reply.
    """

    source: str
    kind: str
    sender: str
    addressed_to_group: bool = True
    qu: bool = False

    @property
    def delivery(self):
        """Delivery type used by rules.

        Returns:
            "unicast" for unicast replies and QU queries, otherwise "broadcast".
        """
        if self.qu or not self.addressed_to_group:
            return "unicast"
        return "broadcast"


def load_rules(text):
    """Parse the rule file's YAML text into rules.

    Args:
        text: The full contents of the rule file.

    Returns:
        A list of Rule objects, in file order.

    Raises:
        ValueError: If the YAML is invalid, a rule is missing a required
            field, or a value is not one of the allowed options.
    """
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"rule file is not valid YAML: {error}") from error
    rules = []
    for entry in data.get("rules", []):
        try:
            action = entry["action"]
            source = entry["source"]
            output = entry["output"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"rule is missing a required field: {entry}") from error
        kind = entry.get("kind", "any")
        delivery = entry.get("delivery", "any")
        if action not in ACTIONS:
            raise ValueError(f"unknown action: {action}")
        if kind not in KINDS:
            raise ValueError(f"unknown kind: {kind}")
        if delivery not in DELIVERIES:
            raise ValueError(f"unknown delivery: {delivery}")
        rules.append(Rule(action, source, output, kind, delivery))
    return rules


def check_networks(rules, networks):
    """Confirm every network a rule names is one the container has.

    Run at startup so a typo in the rule file stops the container before it
    relays anything.

    Args:
        rules: Rules to check, as returned by load_rules.
        networks: Names of the networks the container has.

    Raises:
        ValueError: If any rule names a network not in `networks`.
    """
    known = set(networks)
    unknown = sorted({n for r in rules for n in (r.source, r.output) if n not in known})
    if unknown:
        raise ValueError(f"rules name networks the container does not have: {', '.join(unknown)}")


def _applies(rule, message, output):
    """Check whether a rule covers a message going to one output network.

    Args:
        rule: The rule to check.
        message: The message being decided.
        output: The candidate output network.

    Returns:
        True if the rule's source, output, kind, and delivery all match.
    """
    return (
        rule.source == message.source
        and rule.output == output
        and rule.kind in (message.kind, "any")
        and rule.delivery in (message.delivery, "any")
    )


def decide(rules, message, networks, own_addresses=frozenset()):
    """Return the networks this message should be relayed to.

    Messages sent from one of the mirror's own addresses are never relayed,
    which prevents loops. A message is never sent back to its source network.
    For every other network, the first rule that applies decides, and no
    matching rule means the message is not relayed there.

    Args:
        rules: Rules in file order, as returned by load_rules.
        message: The message to decide.
        networks: Names of all networks the container has.
        own_addresses: Addresses the mirror itself holds.

    Returns:
        The set of output network names the message should be sent to.
        Empty if nothing should be relayed.
    """
    if message.sender in own_addresses:
        return set()
    outputs = set()
    for output in networks:
        if output == message.source:
            continue
        for rule in rules:
            if _applies(rule, message, output):
                if rule.action == "allow":
                    outputs.add(output)
                break
    return outputs
