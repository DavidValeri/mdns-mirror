# 05: Lock down the container

**What to build:** Inside the container, IP forwarding is off, and the only traffic that passes is mDNS on the mDNS port. Everything else is dropped.

**Blocked by:** 03

**Status:** ready-for-agent

- [x] Forwarding is disabled in the container
- [x] Only UDP traffic on port 5353 passes between networks
- [x] Non-mDNS traffic between networks, such as TCP or other ports, is dropped
