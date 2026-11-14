# 01: Pin test tools

**What to build:** The test tools (`pytest`, `ruff`, `pyyaml`) have exact version pins in the project's dev dependency group. The test script installs from that group, so local and CI runs use the same versions.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `pytest`, `ruff`, and `pyyaml` are pinned to exact versions in the dev dependency group
- [ ] The test script installs its tools from the dev dependency group, not unpinned names
- [ ] Running the test script locally passes with the pinned versions
- [ ] `CONTRIBUTING.md` says where the pins live and what to run after bumping one
