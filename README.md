# mDNS Mirror

A containerized service that relays mDNS (Bonjour) traffic between selected
networks, under allow and deny rules. Devices on one network can then
discover services on another without the host routing any other traffic.

The mirror runs in a container on a Linux VM. The VM holds an IP only on
its management network, and the container holds one address on each
mirrored network. See [deploy/vm-setup.md](deploy/vm-setup.md) for the network
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

Run it with Docker Compose. [deploy/vm-setup.md](deploy/vm-setup.md) has the
full Compose file and the VM setup steps. The released image is published to
`ghcr.io/davidvaleri/mdns-mirror` for `linux/amd64` and `linux/arm64`, so you
do not need to build it yourself.

```sh
docker compose up -d
```

To log each mirror decision, add `--verbose` to the container command. See
the Logging section of the setup guide.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev environment, the test
suite, and the branch and commit rules.

## Project layout

| Path | Contents |
| --- | --- |
| `src/mdns_mirror/` | The relay: rule evaluation, packet parsing, sockets, CLI |
| `tests/` | Unit tests, and namespace tests that run the relay end to end |
| `deploy/` | VM setup guide, VLAN check script, firewall rules, and the container entry point |
| `docs/` | Architecture decision records and generated test coverage |
| `scripts/` | Development helpers, such as the test runner |
| `Dockerfile` | Container image |
| `.github/` | GitHub Actions workflows (CI and releases) and Dependabot config |
| `.agents/skills/` | Engineering skills for agent-assisted development |
| `GLOSSARY.md` | Project terms and their meanings |
| `.scratch/mdns-mirror/` | The spec and implementation tickets |

## Documentation

- [VM setup](deploy/vm-setup.md): network layout, Compose file, and verification steps
- [Contributing](CONTRIBUTING.md): dev setup, tests, the branch and commit rules, and releases
- [Releases](CONTRIBUTING.md#releases): how to tag a release and where the image is published
- [Architecture decisions](docs/adr/): why the design is the way it is
- [Glossary](GLOSSARY.md): definitions of network, mirror, advertisement, query, and rule
- [Spec](.scratch/mdns-mirror/spec.md): user stories and implementation decisions

## Limitations

- Linux only. The relay depends on Linux socket options.
- QU and legacy replies are matched to queries by a relay-chosen query ID, with a 5-second window for QU and 2 seconds for legacy queries.
- Legacy queries that carry answer or authority records are dropped.
- The container runs as root, because it needs `NET_ADMIN` to load its firewall rules.
