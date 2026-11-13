# 10: Relayed packets keep source port 5353

**What to build:** Relayed packets are sent from UDP port 5353. Avahi and other standard responders drop responses from any other source port, and treat queries from other ports as legacy unicast, so this is needed for interop. Each interface's listening socket also sends, so there's no separate sender that could receive replies by mistake.

**Blocked by:** 03

**Status:** done

- [x] Relayed multicast packets have source port 5353
- [x] Unicast replies to the mirror arrive on the socket that reads them
- [x] A namespace test checks the source port of a relayed packet
- [x] The QU round-trip test replies to the query's source port, not a hardcoded one
