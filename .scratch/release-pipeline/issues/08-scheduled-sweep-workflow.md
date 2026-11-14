# 08: Scheduled sweep workflow, dry-run by default

**What to build:** A daily workflow, also runnable by hand, lists the package versions, builds the keep set from release-tag manifests, and uses the selection logic to report what it would delete. Manual runs default to dry-run.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] The workflow runs on a daily schedule and on manual dispatch
- [ ] Manual dispatch defaults to dry-run, and nothing is deleted in dry-run
- [ ] The keep set includes the children of every release-tagged version, followed recursively
- [ ] Any failure to read a release-tag manifest stops the run with no deletions
- [ ] The run summary lists each version's digest, tags, age, and whether it is kept or would be deleted
- [ ] The workflow authenticates with its own token, with package read and write permission
