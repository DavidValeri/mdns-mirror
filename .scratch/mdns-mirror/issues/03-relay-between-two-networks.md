# 03: Relay mDNS between two networks

**What to build:** The running container attaches to two networks and relays mDNS between them under the rules, over both IPv4 and IPv6. Tested with real packets in network namespaces joined by veth pairs.

**Blocked by:** 02

**Status:** ready-for-agent

- [x] An allowed advertisement from one network reaches the other network
- [x] A denied advertisement does not reach the other network
- [x] IPv4 (224.0.0.251) and IPv6 (ff02::fb) mDNS are both relayed under the same rules
- [x] Link-local AAAA records are relayed unchanged
