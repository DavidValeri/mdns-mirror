# Contributing

This guide covers setting up a development environment, running the tests,
and the branch and commit rules.

## Development setup

Requirements:

- Python 3.11 or newer
- Docker, for the full test suite

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

The coverage check fails if a spec story or ADR has no covering test, and
it regenerates `docs/testing.md`. Do not edit `docs/testing.md` by hand.

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
