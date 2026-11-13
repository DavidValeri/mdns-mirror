# 09: Relay unicast replies and QU queries

**What to build:** A QU query is relayed to allowed output networks. The unicast reply from a responder is sent back to the original querier on its network, if the rules allow the reply's path. Pending queries expire after 5 seconds.

**Blocked by:** 03

**Status:** done

- [x] A QU query is relayed to the output networks its rules allow
- [x] A unicast reply to the mirror is sent back to the querier when the reverse rule allows it
- [x] A unicast reply is not sent when the reverse rule denies it
- [x] A reply arriving after the 5-second window is not sent
- [x] A reply whose relay ID does not match a pending query is not sent
