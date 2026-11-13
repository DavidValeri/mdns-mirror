# 07: End-to-end test suite

**What to build:** A test suite that runs the container against simulated networks and checks the behavior the spec requires end to end.

**Blocked by:** 03, 05

**Status:** ready-for-agent

- [x] An advertisement reaches only the output networks its rules allow
- [x] A query reaches only the output networks its rules allow
- [x] Unicast TCP traffic, such as SSH to the VM, is never mirrored
- [x] Nothing other than mDNS crosses between simulated networks
- [x] The suite runs without manual setup
