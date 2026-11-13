# 04: Reject bad config at startup

**What to build:** A rule file that doesn't parse, or a rule that names a network the container doesn't have, stops the container with a clear error. The container never runs with a partial policy.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] An unparseable rule file stops startup with an error that names the problem
- [x] A rule naming an unknown network stops startup with an error that names the network
- [x] No mirroring happens after a failed startup
