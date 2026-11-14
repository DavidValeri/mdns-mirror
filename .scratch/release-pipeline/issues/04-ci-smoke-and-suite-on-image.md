# 04: Run smoke test and suite in CI on the built image

**What to build:** The CI image job runs the same smoke test and full suite against the image it builds, so a pull request is checked against the image that would ship.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] The CI image job builds the amd64 image and loads it locally for testing
- [ ] The smoke test runs against that image and fails the job on any failed check
- [ ] The full suite runs against that image and fails the job on any failure
- [ ] The arm64 build remains build-only
- [ ] A failing smoke check or failing test fails the pull request check
