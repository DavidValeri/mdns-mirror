# 08: VM setup guide

**What to build:** A document that lets someone rebuild the Linux VM's network setup from scratch: the management IP, the VLAN subinterfaces, one macvlan per mirrored network, forwarding off, and the container starting on boot. This is documentation rather than code, so it is the one exception to the vertical-slice rule.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Steps cover the management IP on the management VLAN
- [x] Steps cover one VLAN subinterface and one macvlan per mirrored network, with no IP on those networks
- [x] Steps cover disabling IP forwarding on the VM
- [x] Steps cover starting the container on boot
- [x] Steps can be followed without guessing at configuration
