# 06: Log mirror decisions

**What to build:** Each mirror decision is logged with its source network, output network, message kind, and result. Logging is quiet by default and detailed when turned on.

**Blocked by:** 03

**Status:** ready-for-agent

- [x] Each relayed or dropped message produces one log line with source network, output network, message kind, and result
- [x] Default output shows only errors and startup messages
- [x] Detailed per-message logging can be turned on
