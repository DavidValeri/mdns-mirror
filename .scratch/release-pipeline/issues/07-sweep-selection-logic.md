# 07: Sweep selection logic

**What to build:** A pure function takes the list of package versions and the set of digests that release tags still need, and returns the versions the sweep may delete. It never deletes an untagged version younger than 24 hours, anything reachable from a release tag, or anything when its inputs are incomplete.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] An untagged child of a release tag is kept
- [ ] Children of a failed candidate are returned for deletion
- [ ] An orphan older than 24 hours is returned for deletion
- [ ] An orphan younger than 24 hours is kept
- [ ] Missing manifest data for any release tag returns no deletions
- [ ] Indexes are ordered before their children in the result
