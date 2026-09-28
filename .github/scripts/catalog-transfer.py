#!/usr/bin/env python3
"""Move catalog data between runners; never execute artifact content.

The publisher uses this file from the trusted workflow commit, not the artifact.
The artifact is a bounded JSON manifest and flat, SHA-256-named regular blobs.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess


MAX_MANIFEST = 16 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_ENTRIES = 100_000
SHA = re.compile(r"[0-9a-f]{64}")
PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*(?:[.][A-Za-z0-9_-]+)*(?:/[A-Za-z0-9_][A-Za-z0-9_-]*(?:[.][A-Za-z0-9_-]+)*)*")
EXACT_PATHS = {"data/tenders-national-highways.json"} | {
    f"{root}/{kind}-manifest-v1.36.json"
    for root in ("static", "docs", "android-app/www")
    for kind in ("contract", "road-notice", "road-agreement")
}
PREFIXES = (
    "data/gepnic-road-notices/", "data/custom-road-tenders/",
    "data/pmgsy-road-agreements/", "docs/packs/v1/contracts/",
    "docs/packs/v1/road-notices/", "docs/packs/v1/road-agreements/",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def allowed(path):
    return (isinstance(path, str) and len(path) <= 1024 and PATH.fullmatch(path)
            and (path in EXACT_PATHS or (
                path.startswith(PREFIXES) and path.endswith((".json", ".json.gz")))))


def git(root, *args):
    # No shell, hooks, filters, submodules, or artifact-provided Git configuration.
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=root)


def changed_paths(root):
    raw = git(root, "diff", "--no-renames", "--name-only", "-z", "HEAD")
    raw += git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(set(raw.decode("utf-8").split("\0")) - {""})


def safe_target(root, path):
    require(allowed(path), f"Non-catalog or unsafe path: {path!r}")
    target = root / path
    # Check every existing ancestor, even for a deleted file or missing leaf.
    for item in (root, *target.relative_to(root).parents):
        ancestor = item if item == root else root / item
        if ancestor.exists() or ancestor.is_symlink():
            require(stat.S_ISDIR(ancestor.lstat().st_mode), "Unsafe catalog parent")
    if target.exists() or target.is_symlink():
        require(stat.S_ISREG(target.lstat().st_mode), "Catalog must be a regular file")
        require(target.stat().st_nlink == 1, "Hard-linked catalog file")
        if os.name != "nt":
            require(not target.stat().st_mode & 0o111, "Executable catalog file")
    return target


def digest_file(path):
    require(stat.S_ISREG(path.lstat().st_mode), "Blob must be a regular file")
    require(path.stat().st_nlink == 1, "Hard-linked blob")
    require(path.stat().st_size <= MAX_FILE, "Catalog file exceeds limit")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            size += len(block)
            require(size <= MAX_FILE, "Catalog file exceeds limit")
            digest.update(block)
    return size, digest.hexdigest()


def provenance(root):
    expected = {key: os.environ[key] for key in (
        "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY")}
    require(re.fullmatch(r"[0-9a-f]{40}", expected["GITHUB_SHA"]), "Invalid source SHA")
    require(expected["GITHUB_RUN_ID"].isdigit() and
            expected["GITHUB_RUN_ATTEMPT"].isdigit(), "Invalid run identity")
    require(git(root, "rev-parse", "HEAD").decode().strip() == expected["GITHUB_SHA"],
            "Checkout does not match trusted workflow SHA")
    return expected


def capture(root, artifact):
    identity = provenance(root)
    paths = changed_paths(root)
    require(len(paths) <= MAX_ENTRIES, "Too many catalog changes")
    # Validate all paths before creating the transfer; never package repository code.
    targets = [(path, safe_target(root, path)) for path in paths]
    require(not artifact.exists(), "Transfer directory already exists")
    artifact.mkdir(parents=True)
    entries, total = [], 0
    for path, target in targets:
        if not target.exists():
            entries.append({"path": path, "delete": True})
            continue
        size, digest = digest_file(target)
        total += size
        require(total <= MAX_TOTAL, "Catalog transfer exceeds limit")
        shutil.copyfile(target, artifact / digest)
        entries.append({"path": path, "size": size, "sha256": digest})
    manifest = json.dumps({"format": 1, "provenance": identity, "entries": entries},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
    require(len(manifest) <= MAX_MANIFEST, "Transfer manifest exceeds limit")
    (artifact / "manifest.json").write_bytes(manifest)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"changed={'true' if paths else 'false'}\n")
    print(f"Captured {len(paths)} catalog changes ({total} bytes)")


def unique_keys(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate manifest key")
        value[key] = item
    return value


def apply(root, artifact):
    identity = provenance(root)
    require(not changed_paths(root), "Publisher checkout is not clean")
    require(stat.S_ISDIR(artifact.lstat().st_mode), "Unsafe artifact directory")
    manifest_path = artifact / "manifest.json"
    require(stat.S_ISREG(manifest_path.lstat().st_mode), "Unsafe manifest")
    require(manifest_path.stat().st_nlink == 1, "Hard-linked manifest")
    require(manifest_path.stat().st_size <= MAX_MANIFEST, "Transfer manifest exceeds limit")
    manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=unique_keys)
    require(isinstance(manifest, dict) and set(manifest) == {"format", "provenance", "entries"}
            and type(manifest["format"]) is int and manifest["format"] == 1,
            "Invalid transfer format")
    require(manifest["provenance"] == identity, "Artifact provenance mismatch")
    entries = manifest["entries"]
    require(isinstance(entries, list) and 0 < len(entries) <= MAX_ENTRIES,
            "Invalid catalog entry count")
    seen, blobs, plan, total = set(), {"manifest.json"}, [], 0
    for entry in entries:
        require(isinstance(entry, dict) and "path" in entry, "Invalid catalog entry")
        path = entry["path"]
        target = safe_target(root, path)
        require(path not in seen, "Duplicate catalog path")
        seen.add(path)
        if set(entry) == {"path", "delete"}:
            require(entry["delete"] is True and target.is_file(), "Invalid deletion")
            plan.append((path, target, None))
        else:
            require(set(entry) == {"path", "size", "sha256"}, "Invalid file entry")
            size, digest = entry["size"], entry["sha256"]
            require(type(size) is int and 0 <= size <= MAX_FILE, "Invalid catalog size")
            require(isinstance(digest, str) and SHA.fullmatch(digest), "Invalid blob hash")
            total += size
            require(total <= MAX_TOTAL, "Catalog transfer exceeds limit")
            blob = artifact / digest
            require(digest_file(blob) == (size, digest), "Catalog blob integrity mismatch")
            blobs.add(digest)
            plan.append((path, target, blob))
    require({item.name for item in artifact.iterdir()} == blobs, "Unexpected artifact files")
    # All input is validated before the first worktree write. No archives or patches.
    for path, target, blob in plan:
        if blob is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(blob, target)
            target.chmod(0o644)
        git(root, "--literal-pathspecs", "add", "--", path)
    require(set(changed_paths(root)) == seen, "Unexpected staged changes")
    modes = git(root, "diff", "--cached", "--raw", "--no-renames").decode()
    for line in modes.splitlines():
        require(line.split()[1] in ("100644", "000000"), "Unsafe staged file mode")
    git(root, "diff", "--cached", "--check")
    print(f"Validated and staged {len(plan)} catalog changes ({total} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capture", "apply"))
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    try:
        {"capture": capture, "apply": apply}[args.operation](Path.cwd(), args.artifact.absolute())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Catalog transfer refused: {exc}\n")
