"""Check that every spec story and ADR is covered by a test or a manual check.

Tests declare what they verify with @pytest.mark.covers("mdns-mirror:story:17", "adr:0004").
Story IDs are prefixed with the name of their spec folder under .scratch/, so
stories from different specs never share an ID. Requirements that are checked
by hand are listed in MANUAL below, with a reason.

Running this script also regenerates docs/testing.md from the same data.

Exits non-zero if a requirement has no test and no manual entry, a test names
an unknown requirement, a test has no covers marker, or a manual entry is stale.
"""

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "testing.md"

MANUAL = {
    "mdns-mirror:story:1": "Container packaging and VM setup are done by hand. See deploy/vm-setup.md.",
    "mdns-mirror:story:2": "Management IP is set during VM setup. Check with the steps in deploy/vm-setup.md.",
    "mdns-mirror:story:3": "No IP on mirrored networks is set during VM setup. Check with the steps in deploy/vm-setup.md.",
    "mdns-mirror:story:4": "Forwarding is turned off during VM setup. Check with the steps in deploy/vm-setup.md.",
    "mdns-mirror:story:5": "Per-network macvlan attachment is set during VM setup. Check with deploy/vm-setup.md.",
    "mdns-mirror:story:6": "Management-network address is set during VM setup. Check with deploy/vm-setup.md.",
    "mdns-mirror:story:30": "Restart behavior comes from the Compose restart policy. Check by restarting the container after setup.",
    "mdns-mirror:story:31": "Start on boot comes from Docker starting on boot. Check by rebooting the VM after setup.",
    "mdns-mirror:story:32": "Reproducibility is the guide itself. Check by following deploy/vm-setup.md on a fresh VM.",
    "mdns-mirror:story:33": "VLAN mapping is checked by deploy/check-vlans.sh before the container starts.",
    "mdns-mirror:story:34": "A missing VLAN is reported by deploy/check-vlans.sh before the container starts.",
    "mdns-mirror:story:35": "Design review, not a test.",
    "mdns-mirror:story:36": "Design property, not a test.",
    "release-pipeline:story:1": "Release workflow run: the shipped digest is the one the tests ran against. Checked in CI.",
    "release-pipeline:story:2": "Image contents are checked by hand against the Dockerfile's runtime stage.",
    "release-pipeline:story:3": "Release workflow run: the suite runs in the base image that ships. Checked in CI.",
    "release-pipeline:story:4": "Smoke test step in CI (scripts/smoke-test.sh), not pytest.",
    "release-pipeline:story:5": "Smoke test step in CI (scripts/smoke-test.sh), not pytest.",
    "release-pipeline:story:6": "Smoke test step in CI (scripts/smoke-test.sh), not pytest.",
    "release-pipeline:story:7": "Smoke test step in CI (scripts/smoke-test.sh), not pytest.",
    "release-pipeline:story:8": "Release workflow job ordering. Checked by a release run that fails a test.",
    "release-pipeline:story:9": "Release workflow cleanup step. Checked by a failing release run.",
    "release-pipeline:story:10": "Release workflow cleanup under cancellation. Checked by a cancelled release run.",
    "release-pipeline:story:11": "Release workflow step ordering. Checked by a release run.",
    "release-pipeline:story:12": "Release workflow promotes by digest. Checked by a release run.",
    "release-pipeline:story:13": "Release workflow tags. Checked by a release run.",
    "release-pipeline:story:14": "Release workflow pre-release handling. Checked by a pre-release tag run.",
    "release-pipeline:story:15": "Release workflow attestation. Checked by a release run.",
    "release-pipeline:story:22": "Sweep schedule in sweep.yml. Checked by the scheduled run.",
    "release-pipeline:story:23": "Dry-run default is set by the sweep.yml dispatch input. Checked by a manual dispatch.",
    "release-pipeline:story:26": "Local build command. Checked by running it.",
    "release-pipeline:story:27": "Local smoke-test command. Checked by running it.",
    "release-pipeline:story:28": "Local full-suite command. Checked by running it.",
    "release-pipeline:story:29": "Test tool pins live in one place. Checked by reading pyproject.toml.",
    "release-pipeline:story:30": "Pin-bump steps are documented. Checked by reading CONTRIBUTING.md.",
    "release-pipeline:story:31": "Base image pin by digest. Checked by reading the Dockerfile.",
    "release-pipeline:story:32": "Dependabot config. Checked by reading .github/dependabot.yml.",
    "release-pipeline:story:33": "Dependabot config. Checked by reading .github/dependabot.yml.",
    "release-pipeline:story:34": "Release process is documented. Checked by reading CONTRIBUTING.md.",
    "release-pipeline:story:35": "Decision is recorded in docs/adr/0005. Checked by reading the ADR.",
    "release-pipeline:story:36": "Local and CI test paths are documented. Checked by reading CONTRIBUTING.md.",
    "adr:0005": "CI release decision, not a pytest test. Verified in the release workflow run: the test and promote steps must show the same candidate digest, and the shipped image must start without test tools.",
}


def requirements():
    """Read the story IDs and titles from every spec, and the ADR IDs and titles."""
    found = {}
    for spec in sorted((ROOT / ".scratch").glob("*/spec.md")):
        prefix = spec.parent.name
        for number, text in re.findall(r"^(\d+)\. (As an? .+)$", spec.read_text(), re.MULTILINE):
            found[f"{prefix}:story:{int(number)}"] = text if len(text) <= 100 else text[:97] + "..."
    for path in sorted((ROOT / "docs" / "adr").glob("*.md")):
        number = path.name.split("-")[0]
        found[f"adr:{number}"] = path.read_text().splitlines()[0].removeprefix("# ")
    return found


class _Collector:
    """Pytest plugin that records which tests declare each requirement."""

    def __init__(self):
        self.tests = {}
        self.unmarked = set()

    def pytest_collection_finish(self, session):
        for item in session.items:
            name = f"{pathlib.Path(item.path).relative_to(ROOT)}::{item.originalname}"
            markers = list(item.iter_markers("covers"))
            if not markers:
                self.unmarked.add(name)
            for marker in markers:
                for ident in marker.args:
                    self.tests.setdefault(ident, set()).add(name)


def collected_tests():
    """Collect every test, the requirements it declares, and the tests that declare none."""
    collector = _Collector()
    pytest.main(["--collect-only", "-p", "no:cacheprovider", "-p", "no:terminal", str(ROOT / "tests")], plugins=[collector])
    return collector.tests, collector.unmarked


def _sort_key(ident):
    *kind, number = ident.split(":")
    return (":".join(kind), int(number))


def render(reqs, covered):
    """Build the markdown report."""
    lines = [
        "# Test coverage",
        "",
        "Generated by `scripts/check_coverage.py` from the `covers` markers in `tests/` "
        "and the manual list in that script. Do not edit by hand.",
        "",
        "| Requirement | Title | Status | Tests or manual check |",
        "| --- | --- | --- | --- |",
    ]
    for ident in sorted(reqs, key=_sort_key):
        if ident in covered:
            status = "Automated"
            detail = "<br>".join(f"`{name}`" for name in sorted(covered[ident]))
        else:
            status = "Manual"
            detail = MANUAL.get(ident, "")
        lines.append(f"| {ident} | {reqs[ident]} | {status} | {detail} |")
    return "\n".join(lines) + "\n"


def main():
    """Run the check, regenerate the report, and report any problems."""
    reqs = requirements()
    covered, unmarked = collected_tests()
    problems = []
    for name in sorted(unmarked):
        problems.append(f"test has no covers marker: {name}")
    for ident in sorted(covered, key=_sort_key):
        if ident not in reqs:
            problems.append(f"test marks unknown requirement {ident}: {sorted(covered[ident])}")
    for ident in sorted(MANUAL, key=_sort_key):
        if ident not in reqs:
            problems.append(f"manual entry for unknown requirement {ident}")
        elif ident in covered:
            problems.append(f"{ident} has both a manual entry and automated tests; remove one")
    for ident in sorted(reqs, key=_sort_key):
        if ident not in covered and ident not in MANUAL:
            problems.append(f"{ident} has no test or manual entry: {reqs[ident]}")
    REPORT.write_text(render(reqs, covered))
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
