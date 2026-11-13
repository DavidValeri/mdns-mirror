# mDNS Mirror

A containerized service that relays mDNS (Bonjour) traffic between selected
networks, under allow and deny rules. Devices on one network can then
discover services on another without the host routing any other traffic.

The mirror runs in a container on a Linux VM. The VM holds an IP only on
its management network, and the container holds one address on each
mirrored network. See [docs/vm-setup.md](docs/vm-setup.md) for the network
layout.

## Quick start

Rules live in a YAML file, mounted into the container. Each rule names a
source network, an output network, and an action. Rules are checked in
order, and anything no rule allows is denied. The full rule format is in
the [spec](.scratch/mdns-mirror/spec.md).

```yaml
rules:
  - action: allow
    source: eth0
    output: eth1
    kind: advertisement
  - action: deny
    source: eth0
    output: eth2
```

Run it with Docker Compose. [docs/vm-setup.md](docs/vm-setup.md) has the
full Compose file and the VM setup steps.

```sh
docker compose up -d
```

To log each mirror decision, add `--verbose` to the container command. See
the Logging section of the setup guide.

## Development

Requirements: Python 3.11 or newer for local work, and Docker for the
network namespace tests.

Quick local run, without the namespace tests:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

Full run, including the namespace tests, in a privileged Linux container:

```sh
scripts/test.sh
```

The namespace tests create network namespaces and need root, so they only
run on Linux. `scripts/test.sh` runs them inside Docker, so it works on
macOS too. The Avahi interop tests need `avahi-daemon`, which
`scripts/test.sh` installs in the container. They are skipped where it is
not installed.

## Project layout

| Path | Contents |
| --- | --- |
| `src/mdns_mirror/` | The relay: rule evaluation, packet parsing, sockets, CLI |
| `tests/` | Unit tests, and namespace tests that run the relay end to end |
| `deploy/` | Firewall rules and the container entry point |
| `docs/` | VM setup guide and architecture decision records |
| `scripts/` | Helper scripts, such as the test runner |
| `Dockerfile` | Container image |
| `GLOSSARY.md` | Project terms and their meanings |
| `.scratch/mdns-mirror/` | The spec and implementation tickets |

## Documentation

- [VM setup](docs/vm-setup.md): network layout, Compose file, and verification steps
- [Architecture decisions](docs/adr/): why the design is the way it is
- [Glossary](GLOSSARY.md): definitions of network, mirror, advertisement, query, and rule
- [Spec](.scratch/mdns-mirror/spec.md): user stories and implementation decisions

## Limitations

- Linux only. The relay depends on Linux socket options.
- QU and legacy replies are matched to queries by a relay-chosen query ID, with a 5-second window for QU and 2 seconds for legacy queries.
- Legacy queries that carry answer or authority records are dropped.
- The container runs as root, because it needs `NET_ADMIN` to load its firewall rules.
