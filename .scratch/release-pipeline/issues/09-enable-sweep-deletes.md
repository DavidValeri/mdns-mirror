# 09: Enable sweep deletes

**What to build:** After a reviewed dry run on the real package, the sweep is allowed to delete the versions it selects. Deletes are disabled until this ticket is done.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] A dry run on the real package has been reviewed, and its output matches expectations
- [ ] Child manifests of failed candidates are confirmed as kept or deleted correctly
- [ ] Attestation manifests are confirmed as kept or deleted correctly
- [ ] Scheduled runs delete only what the reviewed dry run showed
- [ ] No released version has lost a platform after the first real run
