# 11: Strip link-local records from relayed packets

**What to build:** Link-local A (169.254.0.0/16) and AAAA (fe80::/10) records are removed from the answer and additional sections of relayed packets, matching Avahi. Packets with nothing to remove are forwarded unchanged. Packets that are rebuilt have names written uncompressed and their record counts updated. Malformed packets are dropped. See ADR-0002.

**Blocked by:** 10

**Status:** done

- [x] A link-local AAAA record is removed and a global AAAA record in the same packet is kept
- [x] A link-local A record in the additional section is removed
- [x] A packet with no link-local records is forwarded byte-for-byte
- [x] Compressed names in rdata are rewritten uncompressed, and the packet still parses
- [x] A truncated or malformed packet is rejected
- [x] An end-to-end test confirms a relayed packet has its link-local record removed
