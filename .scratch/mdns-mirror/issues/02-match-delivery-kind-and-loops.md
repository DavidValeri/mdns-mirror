# 02: Match delivery type, message kind, and loop prevention

**What to build:** Rules can allow or deny advertisements and queries separately, and broadcast and unicast separately. A QU query counts as unicast. Messages are never sent back to the network they came from, and messages sent from the mirror's own addresses are never mirrored again.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A rule that allows advertisements does not allow queries, and the reverse
- [x] A rule that allows broadcast does not allow unicast, and the reverse
- [x] A QU query is treated as unicast
- [x] A message is never sent back to its source network
- [x] A message whose source address is one of the mirror's own addresses is never mirrored
