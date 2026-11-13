# 01: Load rules and decide one message

**What to build:** Read the mounted rule file and, for one mDNS message, return the output networks it should be sent to. A message that matches no rule goes nowhere. Rules are checked in order, and the first match wins.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] A rule file defines rules that name a source network and an output network
- [x] A message that matches no rule returns no output networks (default-deny)
- [x] When several rules match, the first in file order decides
- [x] Networks are referred to by container interface name
