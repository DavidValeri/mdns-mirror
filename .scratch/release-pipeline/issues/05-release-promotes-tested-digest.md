# 05: Release only the tested digest

**What to build:** A release pushes the runtime image to a candidate tag named after the commit, tests that exact digest, and only then gives the same digest the version tags. Stable releases also get `X.Y` and `latest`. Pre-releases get only their version tag.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The release job pushes the built image to a `candidate-<sha>` tag before any tests run
- [ ] The smoke test and full suite run against the candidate digest, not a rebuild
- [ ] Promotion adds the version tag to the tested digest
- [ ] Stable releases also get `X.Y` and `latest` on the same digest
- [ ] Pre-releases get only their version tag, never `latest`
- [ ] Attestation and SBOM apply to the promoted digest
- [ ] Promotion is the last registry write in the release job
