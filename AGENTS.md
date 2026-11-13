## Agent skills

### Contributing

Follow `CONTRIBUTING.md` for branches, Conventional Commits, and the dev setup. Work on a feature branch, never directly on `main`. Open pull requests with `gh pr create --base main` from the feature branch, using a Conventional Commits title. Never run `gh pr merge` without explicit approval from the user.

### Issue tracker

Local markdown in `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Test coverage

- Every test that verifies a spec story or ADR carries `@pytest.mark.covers("story:N", "adr:NNNN")`. Use module-level `pytestmark` when a whole file covers the same requirements.
- Every story and ADR needs at least one covering test, or a reason in `MANUAL` in `scripts/check_coverage.py` if it is checked by hand.
- `scripts/check_coverage.py` runs at the end of `scripts/test.sh` and fails on gaps, unknown IDs, or stale manual entries. It also regenerates `docs/testing.md`, which is generated and must not be edited by hand.
- Story and ADR numbers are never renumbered, since the markers depend on them.
