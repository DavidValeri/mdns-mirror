# Contributing

This guide covers setting up a development environment, running the tests,
and the branch and commit rules.

## Development setup

Requirements:

- Python 3.11 or newer
- Docker, for the full test suite
- GitHub CLI (`gh`), optional, for opening pull requests from the terminal

Create a virtual environment and install the package with its dev
dependencies:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install --hook-type pre-commit --hook-type commit-msg
```

The `pre-commit install` step is required once per clone. It installs the
git hooks that check commit messages and block direct commits to `main`.
Run `.venv/bin/pre-commit run --all-files` to check the whole repo.

Run the unit tests and the linter:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

The namespace tests create network namespaces and need root, so they only
run on Linux. Running `pytest` directly on macOS skips or fails them.

## Running the full test suite

Run the full suite with:

```sh
scripts/test.sh
```

The script runs ruff, pytest, and the coverage check inside a privileged
Linux container, so it works on macOS. Docker must be running. The Avahi
interop tests need `avahi-daemon`, which the script installs in the
container. They are skipped where it is not installed.

The test tools (`pytest`, `ruff`, and `pyyaml`) are pinned to exact versions
in the `dev` extra in `pyproject.toml`. Local runs and the test script both
install from that extra. To bump a pin, edit `pyproject.toml`, reinstall with
`.venv/bin/pip install -e ".[dev]"`, and run `scripts/test.sh` before committing.

The coverage check fails if a spec story or ADR has no covering test, and
it regenerates `docs/testing.md`. Do not edit `docs/testing.md` by hand.

## Agent skills

The engineering skills for agent-assisted work are committed under
`.agents/skills/`. They come from `mattpocock/skills`, and their versions are
recorded in `skills-lock.json`. No install step is needed after cloning.

To update them, run `npx skills@latest update`, review the changes, and commit
the result.

## Branches

All changes go through a feature branch and a pull request. Do not commit
directly to `main`.

Name branches `<type>/<kebab-slug>`, where `<type>` is the commit type and
the slug describes the change:

```
feat/mirror-rules
fix/query-id-collision
docs/vm-setup-moved
```

Create the branch from an up-to-date `main`:

```sh
git switch main
git pull
git switch -c feat/mirror-rules
```

## Commit messages

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

- `<type>` is one of `feat`, `fix`, `docs`, `refactor`, `test`, `perf`,
  `build`, `ci`, `chore`, `style`, or `revert`.
- `<scope>` is optional. Use one of the suggested scopes below when it fits.
- `<description>` is a short summary in the imperative mood, lowercase,
  with no trailing period.

Suggested scopes:

| Scope | Covers |
| --- | --- |
| `network` | Network attachment, interfaces, and addresses |
| `rules` | Rule format and evaluation |
| `relay` | Packet parsing, relaying, and query ID handling |
| `deploy` | Container image, Compose file, firewall, and VM setup |
| `docs` | Documentation |
| `tests` | Test suite and test helpers |
| `ci` | Continuous integration |

Examples:

```
feat(rules): allow matching on output network
fix(relay): match QU replies by relay ID
docs(deploy): move VM setup guide
```

## Pull requests

Open a pull request from your feature branch into `main`. The PR is merged
with **squash merge**, so the PR title becomes the commit message on `main`.
Write the PR title in the same Conventional Commits format as the commits.

The easiest way is the GitHub CLI, which needs to be installed and signed in
once:

```sh
brew install gh
gh auth login
gh pr create --base main --title "<type>(<scope>): <description>" --body "<summary>"
```

Without `gh`, push the branch and open the PR from the link git prints, or
from the GitHub web interface.

## Continuous integration

Every pull request into `main` runs two checks in GitHub Actions:

- The full test suite, through `scripts/test.sh`.
- A build of the container image for `linux/amd64` and `linux/arm64`. The image is built but not pushed.

Both must pass before a PR is merged. The workflow is in `.github/workflows/ci.yml`.

## Releases

A release is started by pushing a tag. Tags must be SemVer with a `v` prefix:

- `vX.Y.Z` for a release, such as `v1.2.0`.
- `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N`, or `vX.Y.Z-rc.N` for a pre-release, such as `v1.2.0-rc.1`.

Tag the commit on `main` after the change is merged:

```sh
git switch main
git pull
git tag v1.2.0
git push origin v1.2.0
```

The release workflow in `.github/workflows/release.yml` then:

1. Checks that the tag is valid SemVer and that the commit is reachable from `main`.
2. Runs the test suite.
3. Builds the container image for `linux/amd64` and `linux/arm64`, pushes it to `ghcr.io/davidvaleri/mdns-mirror` with the version tag, and attests its build provenance and SBOM. Releases also get the `X.Y` and `latest` tags. Pre-releases get only their version tag.
4. Creates a GitHub Release with generated notes. Pre-releases are marked as pre-releases.

The image and the GitHub Release run in one job, and that job waits for approval in the `release` environment. Approve the run in the Actions tab after checking it.

## One-time repository setup

These steps are done once by the repository owner. They are not needed for
each development setup.

Add the GitHub remote:

```sh
git remote add origin git@github.com:DavidValeri/mdns-mirror.git
git push -u origin main
```

Then, on GitHub:

1. Open **Settings > Branches** and add a rule for `main`:
   - Require a pull request before merging.
   - Block force pushes.
   - Block deletions.
2. Open **Settings > General** and, under **Pull Requests**, allow only
   **Squash merging**.
3. Open **Settings > Environments**, create an environment named `release`, and add yourself as a required reviewer.
4. Open **Settings > Rules > Rulesets**, create a tag ruleset for `v*`, and restrict tag creation to repository admins.
5. After the first image is pushed, open the package at `github.com/DavidValeri/mdns-mirror/pkgs/container/mdns-mirror` and set its visibility to public, if you want anyone to pull it without signing in.

