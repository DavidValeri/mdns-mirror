Status: ready-for-agent

# mDNS Mirror: selective, containerized mDNS relay between networks

## Problem Statement

Our networks are segmented into separate LANs and VLANs. Devices on one network cannot discover services, such as printers, speakers, and media servers, on another, because mDNS is link-local and does not cross network boundaries. Existing mDNS reflectors either mirror everything, which leaks discovery traffic between networks that should stay separate, or filter only by service type, which can't express "this network may see that network's advertisements, but not its queries." We need a way to relay mDNS between specific networks, under rules that name the source network and the output network, without turning the host into a router.

## Solution

Run a containerized mDNS mirror on a Linux VM. The VM has its own management IP on one VLAN, which is the only address the VM itself holds, so it can be reached over SSH. The container attaches to each mirrored network through its own macvlan interface, and holds an address on each one. The VM does not forward IP traffic. The mirror is the only path that carries mDNS between networks.

The mirror receives mDNS messages on each network and decides, per message, which other networks to send it to. Each decision is made from an ordered list of rules. A rule matches on source network, output network, message kind (advertisement or query), and delivery type (broadcast or unicast). The default is to deny. Rules are read from a mounted YAML file, so changing a rule means editing the file and restarting the container, not rebuilding the image.

The mirror never re-mirrors a message it sent itself, so mirrored traffic cannot loop.

## User Stories

1. As a network operator, I want to run the mDNS mirror as a container, so that I can deploy it the same way on any Linux VM that meets the networking requirements.
2. As a network operator, I want the VM to hold an IP address on the management network, so that I can SSH into it.
3. As a network operator, I want the VM to have no IP address on the mirrored networks, so that the VM can't be used to reach one network from another.
4. As a network operator, I want IP forwarding disabled on the VM, so that the host kernel never routes traffic between networks.
5. As a network operator, I want the container to attach to each mirrored network with its own interface, so that each network is a separate, identifiable attachment.
6. As a network operator, I want the container to have an address on the management network as well, so that the management network can be mirrored like any other.
7. As a network operator, I want to define mirror rules in a YAML file mounted into the container, so that I can change rules without rebuilding the image.
8. As a network operator, I want rules to name source and output networks by their container interface name, so that rules match the attachment I can see on the host.
9. As a network operator, I want rules to be evaluated in order with the first match winning, so that I can read the file top to bottom and know which rule applies.
10. As a network operator, I want mDNS traffic that matches no rule to be denied, so that new networks don't start leaking discovery traffic by default.
11. As a network operator, I want to allow advertisements from one network to another, so that services on the first network are discoverable from the second.
12. As a network operator, I want to deny advertisements from one network to another, so that services on the first network stay hidden from the second.
13. As a network operator, I want to allow queries from one network to another, so that devices on the second network can ask for services on the first.
14. As a network operator, I want to deny queries from one network to another, so that devices on the second network can't probe the first.
15. As a network operator, I want to allow or deny broadcast traffic separately from unicast traffic, so that I can permit multicast discovery while blocking direct replies, or the reverse.
16. As a network operator, I want to allow or deny unicast traffic separately from broadcast traffic, so that a unicast reply to a query can be controlled independently of the query itself.
17. As a network operator, I want a QU query, which asks for a unicast reply, to be treated as unicast, so that its reply is controlled by unicast rules.
18. As a network operator, I want a broadcast advertisement from one network to be mirrored to another network only when a rule allows it, so that advertisements don't cross networks by default.
19. As a network operator, I want the same rule to apply to one source network sending to several output networks, so that I can fan out a source to several destinations with separate rules.
20. As a network operator, I want rules that name one source and one output to be independent of the rules for other pairs, so that changing one pair doesn't affect another.
21. As a network operator, I want the mirror to never send a message back to the network it came from, so that a network doesn't receive its own traffic twice.
22. As a network operator, I want the mirror to drop any message whose source address belongs to the mirror itself, so that a mirrored message cannot be mirrored again in a loop.
23. As a network operator, I want unicast SSH and other TCP traffic to the VM and its networks to never be mirrored, so that mirroring can't interfere with management access.
24. As a network operator, I want only mDNS traffic on the mDNS port to be relayed, so that the mirror cannot become a general-purpose bridge.
25. As a network operator, I want the container's network namespace to drop all traffic except the mDNS traffic it relays, so that the container is locked down beyond its mirror function.
26. As a network operator, I want a rule file that fails to load to stop the container with a clear error, so that the mirror never runs with a partial or unknown policy.
27. As a network operator, I want a rule that references an interface the container doesn't have to be reported as an error at startup, so that I find typos before traffic is affected.
28. As a network operator, I want the container to log every mirror decision with its source network, output network, message kind, and result, so that I can see why a message was or wasn't relayed.
29. As a network operator, I want mirror logs to be quiet by default and detailed on request, so that normal operation doesn't flood the logs.
30. As a network operator, I want to restart the container and have it resume mirroring with the rules on file, so that a restart doesn't require manual steps.
31. As a network operator, I want the container to start on boot with the VM, so that discovery works after a reboot without intervention.
32. As a network operator, I want the VM's network setup to be reproducible from documentation, so that I can rebuild the VM without guessing its configuration.
33. As a network operator, I want the VLAN subinterfaces the container uses to be explicit in the setup, so that I can audit which VLAN each network maps to.
34. As a network operator, I want a clear error if a mirrored network's VLAN is missing on the VM, so that a misconfigured VLAN doesn't silently drop traffic.
35. As a security reviewer, I want the design to show that the VM is the only host between networks and that it cannot route between them, so that I can verify the isolation claim.
36. As a security reviewer, I want the rules to be reviewable as a single file, so that I can audit the full allow and deny policy at once.
37. As a security reviewer, I want default-deny behavior to be tested, so that I can rely on it as a safety property.
38. As a developer, I want to test the mirror decision as a function of network, message kind, delivery type, and rules, so that rule logic is tested quickly without a network.
39. As a developer, I want an end-to-end test that runs the container against simulated networks, so that I can check packet-level behavior before deployment.
40. As a developer, I want the end-to-end test to confirm that an advertisement on one network reaches only the output networks its rules allow, so that routing rules are verified on real packets.
41. As a developer, I want the end-to-end test to confirm that unicast SSH is not mirrored, so that the management path stays unaffected.
42. As a developer, I want the end-to-end test to confirm that the reflection-loop check works, so that mirrored traffic can't cycle.
43. As a network operator, I want IPv6 mDNS to be mirrored under the same rules as IPv4, so that devices on IPv6-only networks can discover services across networks.
44. As a network operator, I want link-local address records removed from relayed packets, so that addresses valid only on their home network don't reach other networks.
45. As a developer, I want relayed packets to come from port 5353, so that standard responders and Avahi accept them.
46. As a legacy client, I want a query sent from a port other than 5353 to get its reply unicast back to my port, so that older clients keep working across networks.
47. As a network operator, I want legacy queries to follow the same rules as other queries, so that the rules still decide what crosses networks.
48. As a legacy client, I want my reply to carry the query ID I sent, so that I can match it to my query.
49. As a developer, I want interop tests against a real Avahi responder, so that problems with standard responders show up before deployment.

## Implementation Decisions

- **Deployment:** the mirror is a container on a Linux VM. Docker bridge networking is not used, because it does not carry mDNS multicast to the physical networks.
- **Network attachment:** each mirrored network is attached to the container through its own macvlan interface, on a VLAN subinterface of the VM's trunk NIC. The VM holds an IP only on the management network. The macvlan limitation (the VM can't reach the container over the same parent interface) is accepted, since the VM does not need to reach the container.
- **Forwarding:** IP forwarding is disabled on the VM and in the container, outside the mirror's own relay path. Mirrored mDNS is the only traffic that crosses between networks.
- **Network identity:** a network is identified by its container interface name. Rules refer to networks by that name.
- **Management network:** the management network is a mirrored network like any other, so its rules are default-deny unless set.
- **Rule model:** a rule matches source network, output network, message kind (advertisement or query), and delivery type (broadcast or unicast). Rules are evaluated in order, first match wins. Default is deny.
- **Delivery types:** broadcast means mDNS traffic to the multicast group. Unicast means unicast replies and QU queries.
- **IP versions:** the mirror relays mDNS over both IPv4 (224.0.0.251) and IPv6 (ff02::fb). Rules apply the same way to both. A message stays within its IP version (IPv4 to IPv4, IPv6 to IPv6), as Avahi does by default. There is no option to cross between versions.
- **Source port:** relayed packets keep source port 5353. The relay's own sockets send them, so no separate sender is needed.
- **Link-local records:** A and AAAA records holding link-local addresses (169.254.0.0/16 and fe80::/10) are removed from relayed packets, as Avahi does. A packet with nothing to remove is forwarded byte-for-byte. Otherwise the packet is rebuilt with every name written uncompressed and the record counts updated. See ADR-0002.
- **Legacy unicast queries:** a query from a port other than 5353 is a legacy query. It is relayed only if it has no answer or authority records, as Avahi requires. Its ID is replaced with one the relay chooses, and it's sent from an ephemeral socket on each output network, so responders reply unicast to the relay. The relay remembers the original ID, querier address, and port for 2 seconds. A reply that comes back with a remembered ID is decided by the rules in the reverse direction (unicast advertisement). If allowed, the original ID is restored and the reply goes to the querier's port, sent from port 5353. See ADR-0003.
- **QU queries:** a QU query is relayed with a relay-chosen ID, shared across output networks, using the same ID allocator as legacy queries. The relay remembers the original ID and querier for 5 seconds. A unicast reply with the relay ID is decided by the rules in the reverse direction. If allowed, the original ID is restored and the reply goes to the querier. Relay IDs never use 0, since most advertisements carry it. See ADR-0004.
- **Configuration:** rules are in a YAML file, mounted into the container at start. Config changes take effect on container restart.
- **Startup validation:** a config file that does not parse, or a rule that names an unknown network, stops the container with an error. The container does not start with a partial policy.
- **Loop prevention:** any message whose source address belongs to one of the mirror's own interfaces is never mirrored. The mirror also never sends a message back to the network it came from.
- **Traffic scope:** the mirror relays only mDNS on the mDNS port. Everything else is dropped by the container's network namespace filter.
- **Logging:** each mirror decision is logged with source network, output network, message kind, and result. Logging is quiet by default.
- **Restart behavior:** the container starts on boot with the VM, and resumes mirroring from the mounted rules.
- **Modules:** the mirror decision logic (the rule evaluator) is a module with a narrow interface: it takes a message's attributes and the rules, and returns the output networks or none. The packet path (receive, decide, send) wraps that module.

## Testing Decisions

- **What makes a good test:** tests check external behavior, meaning which networks a message is sent to given a rule set, not how the decision is computed internally.
- **Primary seam (rule evaluator):** unit-level tests of the mirror decision function. Each test gives a set of rules and a message's attributes, and checks the output networks. Cover default-deny, first-match ordering, separate broadcast and unicast rules, advertisement and query rules, the no-send-back rule, and the loop check.
- **Secondary seam (container boundary):** an end-to-end test that runs the container against network namespaces joined by veth pairs, one per simulated network. It sends real mDNS packets into one network and checks what arrives on the others. It also checks that unicast TCP traffic (SSH) is not mirrored, and that nothing other than mDNS crosses between namespaces.
- **Startup tests:** the container refuses to start with an invalid rule file or an unknown network name.
- **Prior art:** none in this repo yet. The repo currently holds only the agent skills and documentation.
- **Packet rewriting:** unit tests cover packets with nothing to remove (returned unchanged), removed link-local records, names rewritten from compression pointers, and malformed packets (rejected).
- **Source port:** a namespace test checks that relayed packets come from port 5353.
- **Legacy unicast:** namespace tests send legacy queries through the relay to a Python responder, and check the reply comes back with the original ID, and not when the reverse rule denies it. A legacy query with answer or authority records is not relayed, and a reply after the 2-second window is not sent.
- **QU queries:** namespace tests check that a QU reply comes back with the querier's original ID, not when the reverse rule denies it, and that the responder sees a relay ID other than the querier's.
- **Avahi interop:** namespace tests run a real `avahi-daemon` on the far network. They check that a multicast answer is relayed with no link-local records, and that a legacy answer comes back with the original ID. These tests are skipped if `avahi-daemon` isn't installed. The test script installs it in the container.

## Out of Scope

- A web or other UI for managing rules. Rules are edited in the file.
- Service-type filtering, such as allowing only `_airplay._tcp`. Rules match on networks and message kind only.
- Mirroring traffic other than mDNS, such as SSDP or unicast service traffic.
- Running the mirror natively on macOS or Windows. The target is a Linux VM.
- Automatically discovering networks. Each mirrored network is configured explicitly.
- Rewriting records other than removing link-local A and AAAA records (see Further Notes).

## Further Notes

- **Link-local records (resolved):** link-local A and AAAA records are removed from relayed packets, to match Avahi. This reverses the earlier decision to relay them unchanged. See ADR-0002.
- **Legacy unicast (added):** queries from non-5353 ports are relayed as described under Implementation Decisions. Limits: the reply window is 2 seconds, and queries that carry answer or authority records are dropped. See ADR-0003.
- **Known-answer suppression (not planned):** duplicate-answer suppression is out of scope for now. We can add it later if duplicate traffic becomes a problem.
- **Reflect across IP versions (not planned):** the mirror keeps IPv4 and IPv6 separate, with no option to cross between them.
- **Related decision:** see `docs/adr/0001-isolate-networks-at-the-vm.md` for why the VM holds no IP on mirrored networks and forwarding is disabled.
- **Terms:** see `GLOSSARY.md` for the definitions of network, mirror, advertisement, query, broadcast, unicast, rule, default-deny, and reflection loop.
- **Existing tools reviewed:** mdns-repeater, avahi's reflector, and VyOS's mDNS repeater. None of them filters by source and output network pair, and the first two need an IP on every interface. See the alternatives review.
