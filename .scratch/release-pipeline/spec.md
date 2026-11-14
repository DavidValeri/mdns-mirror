**Status:** ready-for-agent

# Release pipeline: test the shipped image, promote the same digest

## Problem Statement

The container image is built and pushed by the release workflow, but nothing runs the image before it ships. The test suite runs against the source tree in a different container than the one we release, so the released bytes are never exercised. The image build in CI also discards its output, so a broken entrypoint, a missing `nft` binary, or a wrong file path in the Dockerfile only shows up when someone pulls the image onto a VM.

The test tools are unpinned, so local and CI runs can drift. A failed release can leave an orphaned image in GHCR with nothing to clean it up. Maintainers have no way to tell which image was tested when a release tag is pushed.

## Solution

Build the runtime image once, push it to a candidate tag, and run the smoke test and the full test suite against that exact digest. Only if both pass is the same digest given the version tags and published as the release. A failed release removes its candidate. A scheduled sweep removes anything a failed or interrupted release left behind, without touching anything a release tag still uses.

The shipped image contains only the runtime. Tests run from outside it. Local developers can build and smoke-test the same image with one command, so what they try matches what CI releases.

## User Stories

1. As a maintainer, I want the release image to be the exact image the tests ran against, so that I know what I shipped was tested.
2. As a maintainer, I want the shipped image to contain only the runtime, so that test tools and test code are not in production.
3. As a maintainer, I want the test suite to run inside the same base image that ships, so that the tested environment matches production.
4. As a maintainer, I want the release to fail if the image cannot start with a valid rules file, so that a broken entrypoint never reaches a VM.
5. As a maintainer, I want the release to fail if the image starts with an invalid rules file without exiting non-zero, so that config errors are never silently ignored.
6. As a maintainer, I want the smoke test to confirm that `nft` is present and the entrypoint is executable, so that packaging mistakes in the Dockerfile are caught.
7. As a maintainer, I want the smoke test to confirm that the firewall rules load inside the container, so that the container is locked down before it runs.
8. As a maintainer, I want the release to stop before publishing if any test fails, so that no version tag points at an untested image.
9. As a maintainer, I want a candidate image removed when its release fails, so that GHCR does not accumulate unused images.
10. As a maintainer, I want a failed cleanup step to still run when the job is cancelled, so that cancelled releases do not leave candidates behind.
11. As a maintainer, I want promotion to be the last registry write, so that cleanup never deletes an image that was already released.
12. As a maintainer, I want release tags added to the same digest rather than a rebuild, so that the tested artifact and the released artifact are identical.
13. As a maintainer, I want the version, `X.Y`, and `latest` tags to point at the tested digest, so that users pulling `latest` get the image that passed.
14. As a maintainer, I want pre-releases to receive only their version tag, so that `latest` never points at a pre-release.
15. As a maintainer, I want attestation and SBOM generation to apply to the promoted digest, so that provenance matches what users pull.
16. As a maintainer, I want the scheduled sweep to delete failed candidate images after 24 hours, so that interrupted releases do not leave orphans for long.
17. As a maintainer, I want the sweep to never delete anything reachable from a release tag, so that a published release cannot lose a platform.
18. As a maintainer, I want the sweep to delete per-platform and attestation child manifests of failed candidates, so that no unreferenced data is left in GHCR.
19. As a maintainer, I want the sweep to delete orphaned children from builds killed before their index was pushed, so that interrupted builds are fully cleaned up.
20. As a maintainer, I want the sweep to leave everything alone if it cannot read the manifest of any release tag, so that a partial view never causes a deletion.
21. As a maintainer, I want the sweep to skip images younger than 24 hours, so that a release in progress is never touched.
22. As a maintainer, I want the sweep to run on a daily schedule, so that cleanup happens without my intervention.
23. As a maintainer, I want to run the sweep manually in dry-run mode by default, so that I can review what it would delete before it deletes anything.
24. As a maintainer, I want the sweep's dry-run output to list each image's digest, tags, age, and whether it is kept or deleted, so that I can verify its decisions.
25. As a maintainer, I want the sweep to write a summary to the workflow run, so that I can review its actions without reading raw logs.
26. As a developer, I want to build the runtime image locally with one command, so that I can try a change before opening a pull request.
27. As a developer, I want the same command to run the smoke test on the locally built image, so that local results match CI.
28. As a developer, I want to run the full test suite against a built image with one command, so that I can reproduce CI results locally.
29. As a developer, I want the test tools installed from pinned versions in one place, so that my local runs and CI runs use the same tools.
30. As a developer, I want the steps for bumping a test tool pin documented, so that I know which file to edit and what to run afterwards.
31. As a developer, I want the base image pinned by digest, so that a rebuild of the same commit produces the same base layers.
32. As a developer, I want Dependabot to propose updates to the pinned base image, so that the pin stays current without manual edits.
33. As a developer, I want Dependabot to propose updates to the pinned test tools, so that the tool pins stay current.
34. As a contributor, I want the release process documented in `CONTRIBUTING.md`, so that I know what happens when I push a tag.
35. As a contributor, I want the decision to promote the tested digest recorded in an ADR, so that future changes to the release process know why it is structured this way.
36. As a contributor, I want the local and CI test paths documented, so that I know how to reproduce a failing CI run.

## Implementation Decisions

- The Dockerfile has a single shipped runtime stage. It contains the package, the firewall rules, the entrypoint, and the `nft` binary, and nothing else. Test tools and test code are not in the shipped image.
- The base image is pinned by digest. Dependabot's Docker ecosystem keeps the pin current.
- Test tool versions (`pytest`, `ruff`, `pyyaml`) are exact pins in the existing `dev` optional dependency group in the Python project metadata. The test runner and CI both install from that group.
- The smoke test and the full suite both run against a specific image digest. The smoke test uses the real entrypoint. The full suite overrides the entrypoint, since the real one starts the relay and needs rule arguments. Tests that need network namespaces run with the capabilities they need, plus unmasked `/proc` paths for the relay's sysctl writes.
- The smoke test has three checks: a valid rules file starts the container and loads the firewall, an invalid rules file makes the container exit non-zero, and `nft` is present with the entrypoint executable.
- The release flow is: validate the tag; build the runtime image and push it to a candidate tag named after the commit SHA; run the smoke test and full suite against the candidate digest; promote the same digest to the version, `X.Y` (stable only), and `latest` (stable only) tags; attest provenance and publish the GitHub Release.
- Promotion is the last tag change. The attestation step adds an attestation to the same digest and does not move a tag. Nothing that deletes images runs before promotion succeeds.
- Failure cleanup runs under an always-run condition, and deletes the candidate version only when promotion did not run.
- The sweep is a scheduled, dispatchable workflow. It lists the package's versions through the owner's user-account container package API. It fetches the manifest of every version with a release tag and collects all child digests, recursively. It deletes untagged versions older than 24 hours whose digests are not in that collected set. It deletes indexes before their children. If any manifest read fails, it deletes nothing. Manual dispatch defaults to dry-run.
- The sweep's selection rule is a pure function of the version list and the manifest-derived keep set. It is kept separate from the workflow so it can be tested on fixture data.
- Local developers use one build-and-smoke-test entry point and one full-suite entry point. CI calls the same entry points, so local and CI runs behave the same.
- Registry authentication uses the workflow's own token with package read and write permission. No long-lived credentials are added.
- The decision to test and promote the same digest, and the choice to keep test tools out of the shipped image, are recorded in a new ADR, not in this spec.

## Testing Decisions

- A good test checks observable behaviour: whether the image starts, whether it exits non-zero on bad input, which tags end up on which digest, and which versions the sweep would delete. Tests do not inspect how the Dockerfile or workflow is written.
- Smoke-test behaviour is tested by running the built image with valid and invalid rules files and checking the exit status and whether the firewall loaded. This is an integration test, run in CI and locally.
- The full test suite is run against the candidate image in CI, and against a locally built image on request. The existing suite's expectations are unchanged.
- The sweep selection rule is tested with fixture version lists and fixture manifest graphs. Cases covered: an untagged child of a release tag is kept, a failed candidate's children are deleted, an orphan older than 24 hours is deleted, an orphan younger than 24 hours is kept, and a manifest read failure deletes nothing.
- Prior art for the tests is the existing namespace tests in `tests/`, which already run in a privileged container, and the fixture-driven unit tests in `tests/`.
- The release and sweep workflows are validated by running them: a dry-run sweep on the real package, and a release from a pre-release tag before any stable tag.
- Stories in this spec are checked by `scripts/check_coverage.py` like the MDNS mirror spec. Stories with no pytest check are listed as manual in that script, with a reason.

## Out of Scope

- Changing the relay's behaviour, rules format, or firewall rules.
- Adding image signing beyond the existing build provenance attestation.
- Publishing to any registry other than GHCR.
- Scanning images for vulnerabilities.
- Building images for platforms other than `linux/amd64` and `linux/arm64`.
- Deleting released versions. The sweep never touches anything reachable from a release tag.
- Changing the VM setup guide, beyond updating image tag references if they change.

## Further Notes

- Seams: the shell entry point that takes an image reference and runs the smoke test and suite is the one place the release flow and local developers meet, so it is the main test seam. The sweep's selection logic is the second seam, kept pure so it does not need a registry. The codebase should have no more seams than these two.
- Open question for the implementer: GHCR's versions API may represent attestation manifests differently from platform manifests. The dry-run output is the first place to confirm they are treated as children. Deletes should stay disabled until a dry run on the real package has been reviewed.
- Candidate tags are kept after promotion, not removed. In GHCR, deleting a tag deletes its version, which would delete the released image. A released version still has a `candidate-*` tag alongside its release tags. The sweep never deletes versions with release tags, and ticket 06 deletes candidates only when promotion did not run.
