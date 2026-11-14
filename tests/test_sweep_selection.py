from datetime import datetime, timedelta, timezone

from sweep_selection import select_deletions

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(hours=48)
YOUNG = NOW - timedelta(hours=1)


def version(digest, *, tags=(), created=OLD, children=(), id=None):
    return {
        "id": id if id is not None else digest,
        "digest": digest,
        "tags": list(tags),
        "created_at": created,
        "children": list(children),
    }


def selected(result):
    return [v["digest"] for v in result]


def test_untagged_child_of_release_is_kept():
    versions = [
        version("sha256:index", tags=["1.2.0"], children=["sha256:amd64"]),
        version("sha256:amd64"),
    ]
    keep = {"sha256:index", "sha256:amd64"}
    assert select_deletions(versions, keep, NOW, complete=True) == []


def test_failed_candidate_and_its_children_are_deleted_index_first():
    versions = [
        version("sha256:amd64", id=2),
        version("sha256:cand", tags=["candidate-abc"], children=["sha256:amd64"], id=1),
    ]
    result = select_deletions(versions, set(), NOW, complete=True)
    assert selected(result) == ["sha256:cand", "sha256:amd64"]


def test_orphan_older_than_24_hours_is_deleted():
    versions = [version("sha256:orphan")]
    assert selected(select_deletions(versions, set(), NOW, complete=True)) == ["sha256:orphan"]


def test_orphan_younger_than_24_hours_is_kept():
    versions = [version("sha256:fresh", created=YOUNG)]
    assert select_deletions(versions, set(), NOW, complete=True) == []


def test_incomplete_manifest_data_deletes_nothing():
    versions = [version("sha256:orphan"), version("sha256:cand", tags=["candidate-abc"])]
    assert select_deletions(versions, set(), NOW, complete=False) == []


def test_released_versions_are_never_deleted():
    versions = [version("sha256:rel", tags=["1.2.0", "latest"])]
    assert select_deletions(versions, set(), NOW, complete=True) == []


def test_nested_children_are_ordered_after_their_parents():
    versions = [
        version("sha256:leaf", id=3),
        version("sha256:mid", children=["sha256:leaf"], id=2),
        version("sha256:top", children=["sha256:mid"], id=1),
    ]
    result = select_deletions(versions, set(), NOW, complete=True)
    assert selected(result) == ["sha256:top", "sha256:mid", "sha256:leaf"]
