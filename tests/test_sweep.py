from datetime import datetime, timedelta, timezone

import pytest
import sweep
from sweep import build_keep_set, build_rows, children_of, fill_children, parse_versions, render_summary
from sweep_selection import select_deletions

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
OLD = "2026-11-10T12:00:00Z"
YOUNG = "2026-11-13T11:00:00Z"


def api_item(id, digest, *, tags=(), created=OLD):
    return {
        "id": id,
        "name": digest,
        "created_at": created,
        "metadata": {"package_type": "container", "container": {"tags": list(tags)}},
    }


def index(*children):
    return {"manifests": [{"digest": c} for c in children]}


def fetcher(manifests, fail=()):
    def fetch(digest):
        if digest in fail or digest not in manifests:
            raise RuntimeError(f"cannot read {digest}")
        return manifests[digest]

    return fetch


@pytest.mark.covers("release-pipeline:story:24")
def test_parse_versions_reads_digest_tags_and_age():
    records = parse_versions([api_item(7, "sha256:a", tags=["1.2.0", "latest"], created=YOUNG)])
    assert records == [
        {
            "id": 7,
            "digest": "sha256:a",
            "tags": ["1.2.0", "latest"],
            "created_at": NOW - timedelta(hours=1),
            "children": [],
        }
    ]


@pytest.mark.covers("release-pipeline:story:24")
def test_parse_versions_handles_untagged_versions():
    records = parse_versions([api_item(1, "sha256:b")])
    assert records[0]["tags"] == []


@pytest.mark.covers("release-pipeline:story:18")
def test_children_of_reads_manifest_list_entries():
    assert children_of(index("sha256:x", "sha256:y")) == ["sha256:x", "sha256:y"]


@pytest.mark.covers("release-pipeline:story:18")
def test_children_of_image_manifest_is_empty():
    assert children_of({"layers": [{"digest": "sha256:layer"}]}) == []


@pytest.mark.covers("release-pipeline:story:17")
def test_keep_set_follows_nested_indexes():
    manifests = {
        "sha256:top": index("sha256:mid", "sha256:attest"),
        "sha256:mid": index("sha256:amd64"),
        "sha256:amd64": {},
        "sha256:attest": {},
    }
    keep, complete = build_keep_set(["sha256:top"], fetcher(manifests))
    assert complete
    assert keep == {"sha256:top", "sha256:mid", "sha256:attest", "sha256:amd64"}


@pytest.mark.covers("release-pipeline:story:20")
def test_keep_set_is_incomplete_when_a_release_manifest_fails():
    manifests = {"sha256:top": index("sha256:amd64"), "sha256:amd64": {}}
    keep, complete = build_keep_set(["sha256:top", "sha256:gone"], fetcher(manifests))
    assert not complete
    assert keep == set()


@pytest.mark.covers("release-pipeline:story:20")
def test_keep_set_is_incomplete_when_a_child_fetch_fails():
    manifests = {"sha256:top": index("sha256:amd64"), "sha256:amd64": {}}
    keep, complete = build_keep_set(["sha256:top"], fetcher(manifests, fail={"sha256:amd64"}))
    assert not complete
    assert keep == set()


@pytest.mark.covers("release-pipeline:story:17")
def test_keep_set_with_no_release_tags_is_empty_and_complete():
    keep, complete = build_keep_set([], fetcher({}))
    assert complete
    assert keep == set()


@pytest.mark.covers("release-pipeline:story:20")
def test_failed_fetch_leaves_every_version_kept_and_deletes_nothing():
    records = parse_versions([api_item(1, "sha256:orphan")])
    keep, complete = build_keep_set(["sha256:gone"], fetcher({}))
    rows = build_rows(records, keep, complete, NOW, set(), dry_run=True)
    assert rows[0]["status"] == "kept"
    assert "nothing deleted" in rows[0]["reason"]


@pytest.mark.covers("release-pipeline:story:16", "release-pipeline:story:24")
def test_dry_run_selection_reports_would_delete_and_candidate_children():
    manifests = {
        "sha256:rel": index("sha256:relamd64"),
        "sha256:relamd64": {},
        "sha256:cand": index("sha256:candamd64"),
        "sha256:candamd64": {},
    }
    items = [
        api_item(1, "sha256:rel", tags=["1.2.0"]),
        api_item(2, "sha256:relamd64"),
        api_item(3, "sha256:cand", tags=["candidate-abc"]),
        api_item(4, "sha256:candamd64"),
        api_item(5, "sha256:fresh", created=YOUNG),
    ]
    records = parse_versions(items)
    fetch = fetcher(manifests)
    keep, complete = build_keep_set([r["digest"] for r in records if r["tags"] == ["1.2.0"]], fetch)
    fill_children(records, fetch)

    selected = select_deletions(records, keep, NOW, complete)
    selected_ids = {r["id"] for r in selected}
    rows = build_rows(records, keep, complete, NOW, selected_ids, dry_run=True)

    assert [r["digest"] for r in selected] == ["sha256:cand", "sha256:candamd64"]
    statuses = {r["digest"]: r["status"] for r in rows}
    assert statuses["sha256:cand"] == "would delete"
    assert statuses["sha256:candamd64"] == "would delete"
    assert statuses["sha256:rel"] == "kept"
    assert statuses["sha256:relamd64"] == "kept"
    assert statuses["sha256:fresh"] == "kept"


@pytest.mark.parametrize(
    ("dry_run", "status"),
    [(True, "would delete"), (False, "deleted")],
)
@pytest.mark.covers("release-pipeline:story:24")
def test_status_reflects_dry_run(dry_run, status):
    records = parse_versions([api_item(1, "sha256:orphan")])
    rows = build_rows(records, set(), True, NOW, {1}, dry_run=dry_run)
    assert rows[0]["status"] == status


@pytest.mark.covers("release-pipeline:story:20")
def test_fill_children_reports_unreadable_manifest_as_incomplete():
    records = parse_versions([api_item(1, "sha256:top"), api_item(2, "sha256:bad")])
    fetch = fetcher({"sha256:top": index("sha256:amd64")}, fail={"sha256:bad"})
    complete = fill_children(records, fetch)
    assert not complete
    assert records[0]["children"] == ["sha256:amd64"]


@pytest.mark.covers("release-pipeline:story:20")
def test_unreadable_child_manifest_makes_run_incomplete_and_deletes_nothing():
    records = parse_versions([api_item(1, "sha256:cand", tags=["candidate-abc"], created=OLD)])
    complete = fill_children(records, fetcher({}))
    selected = select_deletions(records, set(), NOW, complete)
    rows = build_rows(records, set(), complete, NOW, {1}, dry_run=False)
    assert selected == []
    assert rows[0]["status"] == "kept"
    assert "nothing deleted" in rows[0]["reason"]


@pytest.mark.covers("release-pipeline:story:24")
def test_dry_run_reason_states_the_age_limit_in_use(monkeypatch):
    monkeypatch.setattr(sweep, "MIN_AGE", timedelta(hours=2))
    records = parse_versions([api_item(1, "sha256:orphan")])
    rows = build_rows(records, set(), True, NOW, {1}, dry_run=True)
    assert "older than 2 hours" in rows[0]["reason"]


@pytest.mark.covers("release-pipeline:story:24", "release-pipeline:story:25")
def test_summary_lists_each_version_with_status_and_reason():
    records = parse_versions([api_item(1, "sha256:orphan")])
    rows = build_rows(records, set(), True, NOW, {1}, dry_run=True)
    summary = render_summary(rows, dry_run=True)
    assert "dry run, nothing deleted" in summary
    assert "| `sha256:orphan` | (untagged) | 72h | would delete |" in summary
