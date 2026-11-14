# 02: Build and smoke-test the runtime image locally

**What to build:** A developer can build the runtime image with one command, pinned to a base image digest, and run the smoke test against it. The smoke test checks that the image starts with a valid rules file, exits non-zero with an invalid one, and has `nft` with an executable entrypoint.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The base image is pinned by digest, and Dependabot is configured to update the pin
- [x] One command builds the runtime image for the host architecture
- [x] The smoke test passes on a valid rules file: the firewall loads and the process stays up
- [x] The smoke test passes on an invalid rules file: the container exits non-zero
- [x] The smoke test passes on the entrypoint check: `nft` is present and the entrypoint is executable
- [x] `CONTRIBUTING.md` documents the build-and-smoke-test command
