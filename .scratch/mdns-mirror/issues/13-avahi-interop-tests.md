# 13: Interop tests against a real Avahi responder

**What to build:** Namespace tests run `avahi-daemon` on the far network and check that the relay works with it. A multicast answer is relayed with no link-local records. A legacy answer comes back with the original ID. The tests skip when `avahi-daemon` is not installed.

**Blocked by:** 10, 11

**Status:** done

- [x] A multicast answer from Avahi reaches the querier's network
- [x] Link-local records in that answer are removed
- [x] A legacy query to Avahi gets its reply back with the original ID
- [x] The test script installs `avahi-daemon` in the container
