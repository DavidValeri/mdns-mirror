# 03: Run the full suite against a built image locally

**What to build:** A developer can run the full test suite inside the built runtime image with one command. The test tools are installed into a throwaway container from the pinned dev group, and the shipped image is not changed.

**Blocked by:** 01, 02

**Status:** ready-for-agent

- [ ] One command runs the full suite inside the built runtime image
- [ ] Test tools come from the pinned dev group and are not added to the image
- [ ] The shipped image contains no test code or test tools after the run
- [ ] Namespace tests run with the capabilities they need
- [ ] `CONTRIBUTING.md` documents the command and when to use it
