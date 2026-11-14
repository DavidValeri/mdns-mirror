# 06: Clean up the candidate on failure

**What to build:** When a release fails or is cancelled before promotion, its candidate version is deleted from GHCR. Once promotion has run, the candidate is never deleted.

**Blocked by:** 05

**Status:** done

- [x] A cleanup step runs whenever the release job ends, including on cancellation
- [x] The cleanup deletes the candidate version when promotion did not run
- [x] The cleanup does nothing after promotion has succeeded
- [ ] A failing test in the release leaves no candidate version behind
- [ ] A cancelled release leaves no candidate version behind
