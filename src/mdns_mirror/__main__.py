"""Command-line entry point: python -m mdns_mirror.

Usage:
    python -m mdns_mirror --rules RULES.yaml ETH0 ETH1 [...] [--verbose]

Validates the rule file first. If it's invalid, or names a network that
isn't listed, the program exits before relaying anything.
"""

import argparse
import logging
import socket
import sys

from mdns_mirror.relay import run
from mdns_mirror.rules import check_networks, load_rules

log = logging.getLogger("mdns_mirror")


def missing_interfaces(names):
    """Return the names that don't match an interface in this container.

    Args:
        names: Interface names given on the command line.

    Returns:
        A list of names with no matching interface.
    """
    missing = []
    for name in names:
        try:
            socket.if_nametoindex(name)
        except OSError:
            missing.append(name)
    return missing


def main(argv=None):
    """Parse arguments, validate the rules, then start the relay.

    Args:
        argv: Command-line arguments without the program name. Defaults to
            sys.argv[1:] when None.

    Raises:
        SystemExit: On bad arguments, an unsupported platform, or an invalid
            rule file. The exit status is nonzero in each case.
    """
    parser = argparse.ArgumentParser(prog="mdns-mirror")
    parser.add_argument("--rules", required=True, help="path to the rules YAML file")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every mirror decision")
    parser.add_argument("networks", nargs="+", help="container interface names to mirror between")
    args = parser.parse_args(argv)

    # Startup messages are INFO and show by default. Per-message decisions
    # are DEBUG and only show with --verbose.
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # The relay depends on Linux-only socket options, such as SO_BINDTODEVICE.
    if not sys.platform.startswith("linux"):
        parser.error("mdns-mirror only runs on Linux")

    try:
        with open(args.rules) as f:
            rules = load_rules(f.read())
        check_networks(rules, args.networks)
    except (OSError, ValueError) as error:
        parser.exit(1, f"mdns-mirror: {error}\n")

    absent = missing_interfaces(args.networks)
    if absent:
        parser.exit(
            1,
            f"mdns-mirror: no network interface named {', '.join(absent)} in this container. "
            "Check the container's network attachments and the interface names in the command.\n",
        )

    log.info("mirroring mDNS between %s with %d rules", ", ".join(args.networks), len(rules))
    run(rules, args.networks)


if __name__ == "__main__":
    main()
