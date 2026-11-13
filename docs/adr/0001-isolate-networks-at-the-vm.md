# Isolate networks at the VM; mirror is the only path between LANs

The mirror VM holds an IP only on the management network. Each mirrored network is attached to the container through its own macvlan interface, without an IP on the VM. IP forwarding on the VM is disabled. Mirrored mDNS is the only traffic that crosses between networks. We chose this over giving the VM an IP on every LAN because a routing VM would be a second, unfiltered path between networks, and because macvlan keeps mDNS multicast working where Docker bridge networking does not.
