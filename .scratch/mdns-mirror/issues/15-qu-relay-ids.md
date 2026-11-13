# 15: Relay QU queries with relay-chosen IDs

**What to build:** A QU query is relayed with a relay-chosen ID, shared across output networks, instead of the querier's ID. A unicast reply with that ID is sent back to the querier with the querier's original ID restored. Relay IDs never use 0, and legacy and QU queries share one ID allocator. See ADR-0004.

**Blocked by:** 09, 14

**Status:** done

- [x] A QU query is relayed with a relay ID that is shared across output networks
- [x] A unicast reply is sent back to the querier with the original ID restored
- [x] A reply with a different relay ID is not sent
- [x] Relay IDs never use 0
- [x] Legacy and QU queries share one ID allocator, so they never use the same live ID
