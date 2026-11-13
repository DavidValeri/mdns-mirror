# 12: Clear startup errors for missing interfaces and VLANs, and a loop-check test

**What to build:** The container refuses to start, with a clear message, when a named interface doesn't exist. A preflight script run on the VM names any VLAN interface that is missing. An end-to-end test confirms a mirrored message isn't mirrored back in a loop.

**Blocked by:** 04, 07

**Status:** done

- [x] Startup names each interface that doesn't exist and exits nonzero, before relaying
- [x] `scripts/check-vlans.sh` lists missing VLAN interfaces and exits nonzero
- [x] The VM setup guide runs the preflight check before starting the container
- [x] An end-to-end test with rules allowing traffic both ways confirms the receiver gets one copy, not a loop
