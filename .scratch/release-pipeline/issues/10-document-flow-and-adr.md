# 10: Document the flow and record the ADR

**What to build:** Contributors can find how to test locally, how a release is promoted and cleaned up, and how the sweep works. The decision to test and promote the same digest is recorded in an ADR, with a manual coverage entry so the coverage check accepts it.

**Blocked by:** 05, 06, 08

**Status:** done

- [x] `CONTRIBUTING.md` describes the release flow: candidate, test, promote, cleanup
- [x] `CONTRIBUTING.md` describes the sweep: schedule, dry-run default, and what it keeps
- [x] A new ADR records the decision to test and promote the same digest and to keep test tools out of the shipped image
- [x] The ADR has a manual entry in the coverage check with a reason
- [x] The coverage check passes with the new ADR
