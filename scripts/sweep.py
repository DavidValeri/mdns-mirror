"""Sweep orphaned and failed candidate versions of the GHCR mdns-mirror image.

Run by .github/workflows/sweep.yml. The pure functions take already-fetched
data so they can be tested with fixtures. main() does the registry I/O.
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

from sweep_selection import MIN_AGE, is_released, select_deletions

PACKAGE = "mdns-mirror"
API = "https://api.github.com"
PER_PAGE = 100


def parse_versions(items):
    """Turn package version API items into selection records.

    Args:
        items: Version objects from the packages API.

    Returns:
        One record per version, with empty children. The caller fills children
        from manifests.
    """
    records = []
    for item in items:
        tags = item.get("metadata", {}).get("container", {}).get("tags", [])
        records.append(
            {
                "id": item["id"],
                "digest": item["name"],
                "tags": list(tags),
                "created_at": _parse_time(item["created_at"]),
                "children": [],
            }
        )
    return records


def children_of(manifest):
    """Return the digests of the manifests an index points at."""
    return [m["digest"] for m in manifest.get("manifests", [])]


def fill_children(records, fetch):
    """Set each record's children from its manifest.

    Returns:
        True if every manifest was read. False if any read failed. A failed
        read leaves that record's children empty, and the caller must then
        delete nothing, since the children are needed to protect versions.
    """
    complete = True
    for record in records:
        try:
            record["children"] = children_of(fetch(record["digest"]))
        except Exception:
            complete = False
    return complete


def build_keep_set(released_digests, fetch):
    """Collect every digest that release tags still need.

    Args:
        released_digests: Digests of versions that carry a release tag.
        fetch: Callable taking a digest and returning its parsed manifest.
            It may raise on failure.

    Returns:
        A tuple of the keep set and a flag that is False if any manifest
        could not be read. In that case the keep set is empty.
    """
    keep = set()
    pending = list(released_digests)
    while pending:
        digest = pending.pop()
        if digest in keep:
            continue
        keep.add(digest)
        try:
            manifest = fetch(digest)
        except Exception:
            return set(), False
        pending.extend(children_of(manifest))
    return keep, True


def decide(record, keep, complete, now):
    """Return why a version must be kept, or None if it may be deleted.

    Args:
        record: A version record.
        keep: The keep set from build_keep_set.
        complete: The flag from build_keep_set.
        now: The current time, timezone-aware.

    Returns:
        A reason string when the version is kept, otherwise None.
    """
    if is_released(record):
        return "release tag"
    if not complete:
        return "manifest read failed, nothing deleted"
    if record["digest"] in keep:
        return "child of a release tag"
    if now - record["created_at"] < MIN_AGE:
        return f"younger than {_hours_text(MIN_AGE)}"
    return None


def build_rows(records, keep, complete, now, selected_ids, dry_run):
    """Describe each version and what the sweep did or would do to it.

    Args:
        records: Version records.
        keep: The keep set from build_keep_set.
        complete: The flag from build_keep_set.
        now: The current time, timezone-aware.
        selected_ids: IDs selected for deletion.
        dry_run: True if nothing was deleted.

    Returns:
        A list of rows with digest, tags, age, status, and reason keys.
    """
    rows = []
    for record in records:
        reason = decide(record, keep, complete, now)
        if reason is not None:
            status = "kept"
        elif record["id"] in selected_ids:
            status = "would delete" if dry_run else "deleted"
            reason = f"no release tag or kept child, older than {_hours_text(MIN_AGE)}"
        else:
            status = "kept"
            reason = "not selected"
        rows.append(
            {
                "digest": record["digest"],
                "tags": ", ".join(record["tags"]) or "(untagged)",
                "age": _age(now - record["created_at"]),
                "status": status,
                "reason": reason,
            }
        )
    return rows


def render_summary(rows, dry_run):
    """Return the job summary as Markdown.

    Args:
        rows: Rows from build_rows.
        dry_run: True if this run was a dry run.

    Returns:
        The Markdown text.
    """
    mode = "dry run, nothing deleted" if dry_run else "live run"
    lines = [
        f"## Package sweep ({mode})",
        "",
        "| Digest | Tags | Age | Status | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['digest']}` | {row['tags']} | {row['age']} | "
            f"{row['status']} | {row['reason']} |"
        )
    return "\n".join(lines) + "\n"


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age(delta):
    hours = int(delta.total_seconds() // 3600)
    return f"{hours}h"


def _hours_text(delta):
    return f"{int(delta.total_seconds() // 3600)} hours"


def list_versions(owner, token):
    """Return every container version of the package, across all pages."""
    items = []
    page = 1
    while True:
        url = (
            f"{API}/users/{owner}/packages/container/{PACKAGE}/versions"
            f"?per_page={PER_PAGE}&page={page}"
        )
        batch = _api("GET", url, token)
        items.extend(batch)
        if len(batch) < PER_PAGE:
            return items
        page += 1


def delete_version(owner, token, version_id):
    """Delete one container version by ID."""
    url = f"{API}/users/{owner}/packages/container/{PACKAGE}/versions/{version_id}"
    _api("DELETE", url, token)


def fetch_manifest(image, digest):
    """Return the raw manifest for a digest, read through docker buildx."""
    out = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", "--raw", f"{image}@{digest}"],
        check=True,
        capture_output=True,
    ).stdout
    return json.loads(out)


def _api(method, url, token):
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request) as response:
        body = response.read()
    return json.loads(body) if body else None


def main():
    """Run the sweep. Set DRY_RUN, OWNER, GITHUB_TOKEN, and GITHUB_STEP_SUMMARY."""
    dry_run = os.environ.get("DRY_RUN", "true") == "true"
    owner = os.environ["OWNER"]
    token = os.environ["GITHUB_TOKEN"]
    image = f"ghcr.io/{owner}/{PACKAGE}"

    records = parse_versions(list_versions(owner, token))
    cache = {}

    def fetch(digest):
        if digest not in cache:
            cache[digest] = fetch_manifest(image, digest)
        return cache[digest]

    released = [r["digest"] for r in records if is_released(r)]
    keep, complete = build_keep_set(released, fetch)

    complete = fill_children(records, fetch) and complete

    now = datetime.now(timezone.utc)
    selected = select_deletions(records, keep, now, complete)
    if not dry_run:
        for record in selected:
            delete_version(owner, token, record["id"])

    selected_ids = {record["id"] for record in selected}
    rows = build_rows(records, keep, complete, now, selected_ids, dry_run)
    summary = render_summary(rows, dry_run)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary)
    sys.stdout.write(summary)


if __name__ == "__main__":
    main()
