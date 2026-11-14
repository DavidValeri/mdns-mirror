"""Select which GHCR package versions the sweep may delete.

The selection is a pure function over version records, so it can be tested
without a registry. The caller supplies the keep set: every digest that a
release tag still needs, including the children of those manifests.
"""

from datetime import datetime, timedelta

MIN_AGE = timedelta(hours=24)


def select_deletions(versions, keep, now, complete, min_age=MIN_AGE):
    """Return the versions that may be deleted, parents before children.

    Args:
        versions: Records with "digest", "tags", "created_at", "children",
            and "id" keys.
        keep: Digests that release tags still need.
        now: The current time, timezone-aware.
        complete: False if any release-tag manifest could not be read. Nothing
            is deleted in that case.
        min_age: Untagged versions younger than this are never deleted.

    Returns:
        The versions to delete. An index always comes before its children.
    """
    if not complete:
        return []

    eligible = [
        v
        for v in versions
        if not _is_released(v)
        and v["digest"] not in keep
        and now - v["created_at"] >= min_age
    ]
    return _parents_first(eligible)


def _is_released(version):
    return any(not tag.startswith("candidate-") for tag in version["tags"])


def _parents_first(versions):
    remaining = list(versions)
    ordered = []
    while remaining:
        referenced = {child for v in remaining for child in v["children"]}
        roots = [v for v in remaining if v["digest"] not in referenced]
        if not roots:
            roots = remaining
        ordered.extend(roots)
        remaining = [v for v in remaining if v not in roots]
    return ordered
