# 14: Relay legacy unicast queries

**What to build:** Queries sent from a port other than 5353 are relayed to the allowed networks with a relay-chosen ID, and replies come back to the querier with the original ID. Queries that carry answer or authority records are dropped. See ADR-0003.

**Blocked by:** 03

**Status:** done

- [x] A legacy query is relayed to the output networks its rules allow
- [x] A reply comes back to the querier with the original ID
- [x] A reply is not sent when the reverse rule denies it
- [x] A legacy query with answer or authority records is dropped
- [x] A reply after the 2-second window is not sent
