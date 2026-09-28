#!/usr/bin/env python3
"""Offline SEC-007 workflow contracts and hostile catalog-transfer tests."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/refresh-public-road-catalogs.yml"
SPEC = importlib.util.spec_from_file_location(
    "catalog_transfer", ROOT / ".github/scripts/catalog-transfer.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowSecurityTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()
        self.jobs = dict(re.findall(
            r"^  (preflight|refresh|publish):\n(.*?)(?=^  \w+:\n|\Z)",
            self.text.split("jobs:\n", 1)[1], flags=re.M | re.S))

    def test_default_deny_and_write_isolation(self):
        self.assertIn("permissions: {}", self.text.split("jobs:\n")[0])
        for job in ("preflight", "refresh"):
            self.assertRegex(self.jobs[job], r"permissions:\n      contents: read\n    (steps|outputs):")
            self.assertNotIn("GH_TOKEN", self.jobs[job])
            self.assertNotIn(": write", self.jobs[job])
        self.assertIn("permissions:\n      contents: write\n      pull-requests: write", self.jobs["publish"])
        self.assertEqual(self.text.count("GH_TOKEN: ${{ github.token }}"), 1)

    def test_pr_has_only_offline_preflight(self):
        self.assertIn("  pull_request:\n", self.text)
        self.assertNotIn("pull_request_target", self.text)
        self.assertNotIn("workflow_run", self.text)
        self.assertIn("if: ${{ github.event_name == 'pull_request' }}", self.jobs["preflight"])
        for forbidden in ("pip install", "playwright install", "git push", "gh pr create", "secrets."):
            self.assertNotIn(forbidden, self.jobs["preflight"])

    def test_refresh_and_publish_require_trusted_main_trigger(self):
        for job in ("refresh", "publish"):
            condition = re.search(r"^    if: (.*)$", self.jobs[job], re.M).group(1)
            self.assertIn("github.ref == 'refs/heads/main'", condition)
            self.assertIn("(github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')", condition)
        self.assertIn("needs: refresh", self.jobs["publish"])
        self.assertIn("needs.refresh.result == 'success' && needs.refresh.outputs.changed == 'true'", self.jobs["publish"])

    def test_all_actions_are_sha_pinned_and_checkout_does_not_persist(self):
        uses = re.findall(r"uses: (\S+)", self.text)
        self.assertEqual(len(uses), 8)
        for action in uses:
            self.assertRegex(action, r"^[\w-]+/[\w-]+@[0-9a-f]{40}$")
        self.assertEqual(self.text.count("persist-credentials: false"), 3)
        self.assertNotIn("persist-credentials: true", self.text)
        for job in ("refresh", "publish"):
            self.assertIn("ref: ${{ github.sha }}", self.jobs[job])
        self.assertIn("fetch-depth: 0", self.jobs["refresh"])
        self.assertIn("fetch-tags: true", self.jobs["refresh"])
        self.assertNotIn("fetch-depth: 0", self.jobs["publish"])

    def test_locked_wheel_and_browser_install(self):
        lock = (ROOT / ".github/catalog-refresh-requirements.txt").read_text()
        packages = re.findall(r"^([\w_-]+)==([\d.]+) \\\n    --hash=sha256:([0-9a-f]{64})$", lock, re.M)
        self.assertEqual({item[0] for item in packages}, {"playwright", "pyee", "greenlet", "typing_extensions"})
        self.assertIn("--require-hashes --only-binary=:all:", self.jobs["refresh"])
        self.assertIn("playwright install --only-shell chromium", self.jobs["refresh"])
        self.assertNotIn("--with-deps", self.text)
        self.assertEqual(self.text.count('python-version: "3.12.12"'), 3)
        self.assertNotIn("pip install", self.jobs["publish"])
        self.assertNotIn("playwright", self.jobs["publish"])

    def test_artifact_is_same_run_and_never_executes(self):
        artifact_name = "name: public-road-catalog-${{ github.run_id }}-${{ github.run_attempt }}"
        self.assertEqual(self.text.count(artifact_name), 2)
        self.assertNotIn("run-id:", self.jobs["publish"])
        self.assertNotIn("repository:", self.jobs["publish"])
        self.assertIn('catalog-transfer.py apply "$RUNNER_TEMP/catalog-transfer"', self.jobs["publish"])
        self.assertNotRegex(self.jobs["publish"], r"(?:source|bash|python3)\s+\"?\$RUNNER_TEMP/")

    def test_shell_inputs_and_token_handling(self):
        runs = re.findall(r"        run: \|\n(.*?)(?=^      - |^  \w+:|\Z)", self.text, re.M | re.S)
        for script in runs:
            self.assertNotIn("${{", script)
            self.assertIn("set -euo pipefail", script)
        self.assertIn('[[ "$GITHUB_RUN_ID" =~ ^[0-9]+$ ]]', self.text)
        self.assertIn('[[ "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ ]]', self.text)
        self.assertIn('push --set-upstream origin "$catalog_branch"', self.text)
        self.assertIn("GIT_CONFIG_COUNT=1", self.text)
        self.assertIn("::add-mask::$catalog_auth", self.text)
        self.assertNotIn("git config http", self.text)
        self.assertNotIn("gh auth setup-git", self.text)
        self.assertNotIn("--force", self.text)
        self.assertIn("core.hooksPath=/dev/null", self.text)


class CatalogTransferTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sec007-")
        self.addCleanup(self.temp.cleanup)
        # Ignore host Git configuration in synthetic test repositories.
        self.git_environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        })
        self.git_environment.start()
        self.addCleanup(self.git_environment.stop)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.command(self.source, "init", "--quiet")
        self.command(self.source, "config", "core.autocrlf", "false")
        self.command(self.source, "config", "user.name", "SEC007 Test Fixture")
        self.command(self.source, "config", "user.email", "fixture@example.invalid")
        self.first = "data/tenders-national-highways.json"
        self.deleted = "data/custom-road-tenders/gj/old.json"
        self.new = "docs/packs/v1/contracts/gj/new.json"
        self.write(self.source, self.first, b'{"old":1}\n')
        self.write(self.source, self.deleted, b'{}\n')
        self.write(self.source, "trusted.py", b'raise RuntimeError("must not execute")\n')
        self.command(self.source, "add", ".")
        tree = self.command(self.source, "write-tree").strip()
        # Synthetic fixture object only; never commit in the project working tree.
        sha = self.command(self.source, "commit-tree", tree, "-m", "test fixture").strip()
        self.command(self.source, "update-ref", "HEAD", sha)
        self.publisher = self.base / "publisher"
        subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "--quiet", "--no-hardlinks", str(self.source),
                        str(self.publisher)], check=True, capture_output=True)
        self.command(self.publisher, "config", "core.autocrlf", "false")
        self.artifact = self.base / "artifact"
        self.output = self.base / "output.txt"
        self.environment = patch.dict(os.environ, {
            "GITHUB_SHA": sha, "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_OUTPUT": str(self.output),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.write(self.source, self.first, b'{"new":2}\n')
        (self.source / self.deleted).unlink()
        self.write(self.source, self.new, b'{"newpack":3}\n')
        with redirect_stdout(io.StringIO()):
            MODULE.capture(self.source, self.artifact)

    def command(self, root, *args):
        return subprocess.check_output(["git", *args], cwd=root).decode().strip()

    def write(self, root, path, data):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def mutate(self, change):
        path = self.artifact / "manifest.json"
        manifest = json.loads(path.read_bytes())
        change(manifest)
        path.write_text(json.dumps(manifest))

    def rejected(self, message):
        with self.assertRaisesRegex((ValueError, OSError), message):
            MODULE.apply(self.publisher, self.artifact)
        # Hostile input must not change even the first catalog before rejection.
        self.assertEqual((self.publisher / self.first).read_bytes(), b'{"old":1}\n')
        self.assertEqual(MODULE.changed_paths(self.publisher), [])

    def test_round_trip_add_modify_delete_and_stage(self):
        with redirect_stdout(io.StringIO()):
            MODULE.apply(self.publisher, self.artifact)
        self.assertEqual((self.publisher / self.first).read_bytes(), b'{"new":2}\n')
        self.assertFalse((self.publisher / self.deleted).exists())
        self.assertEqual((self.publisher / self.new).read_bytes(), b'{"newpack":3}\n')
        self.assertEqual(set(MODULE.changed_paths(self.publisher)), {self.first, self.deleted, self.new})
        self.assertEqual(self.command(self.publisher, "diff", "--name-only"), "")
        self.assertEqual(self.output.read_text(), "changed=true\n")

    def test_empty_refresh_does_not_request_publication(self):
        output = self.base / "empty-output.txt"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), redirect_stdout(io.StringIO()):
            MODULE.capture(self.publisher, self.base / "empty")
        self.assertEqual(output.read_text(), "changed=false\n")

    def test_capture_rejects_non_catalog_changes(self):
        self.write(self.source, "trusted.py", b'print("replaced")\n')
        with self.assertRaisesRegex(ValueError, "Non-catalog"):
            MODULE.capture(self.source, self.base / "bad-capture")
        self.assertFalse((self.base / "bad-capture").exists())

    def test_hostile_path_variants_fail_before_any_write(self):
        original = (self.artifact / "manifest.json").read_bytes()
        for path in (".github/workflows/evil.yml", "data/custom-road-tenders/../evil.json",
                     "data/custom-road-tenders/.gitattributes", "data/custom-road-tenders/run.py",
                     "data/custom-road-tenders/-option.json", "/tmp/evil.json",
                     "data/custom-road-tenders/x\n.json", "data/custom-road-tenders/x\\evil.json"):
            with self.subTest(path=path):
                (self.artifact / "manifest.json").write_bytes(original)
                self.mutate(lambda m: m["entries"][-1].update(path=path))
                self.rejected("Non-catalog")

    def test_provenance_must_match_run_attempt_repository_and_source(self):
        original = (self.artifact / "manifest.json").read_bytes()
        for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY"):
            with self.subTest(key=key):
                (self.artifact / "manifest.json").write_bytes(original)
                self.mutate(lambda m: m["provenance"].update({key: "foreign"}))
                self.rejected("provenance mismatch")

    def test_wrong_checkout_source_is_rejected(self):
        with patch.dict(os.environ, {"GITHUB_SHA": "0" * 40}):
            self.rejected("Checkout does not match")

    def test_hash_mismatch(self):
        blob = next(path for path in self.artifact.iterdir() if path.name != "manifest.json")
        blob.write_bytes(b'changed\n')
        self.rejected("integrity mismatch")

    def test_unknown_artifact_file(self):
        (self.artifact / "payload.py").write_text("print('never execute')")
        self.rejected("Unexpected artifact")

    def test_duplicate_entry(self):
        self.mutate(lambda m: m["entries"].append(m["entries"][0]))
        self.rejected("Duplicate catalog")

    def test_duplicate_manifest_key(self):
        path = self.artifact / "manifest.json"
        path.write_bytes(path.read_bytes().replace(b'"format":1', b'"format":1,"format":1'))
        self.rejected("Duplicate manifest key")

    def test_unknown_entry_fields_or_modes(self):
        self.mutate(lambda m: m["entries"][0].update(mode="100755"))
        self.rejected("Invalid (file entry|deletion)")

    def test_boolean_size_is_invalid(self):
        self.mutate(lambda m: next(e for e in m["entries"] if "size" in e).update(size=True))
        self.rejected("Invalid catalog size")

    def test_individual_and_total_limits(self):
        with patch.object(MODULE, "MAX_FILE", 1):
            self.rejected("Invalid catalog size")
        with patch.object(MODULE, "MAX_TOTAL", 1):
            self.rejected("transfer exceeds limit")

    def test_manifest_and_entry_limits(self):
        with patch.object(MODULE, "MAX_MANIFEST", 1):
            self.rejected("manifest exceeds limit")
        with patch.object(MODULE, "MAX_ENTRIES", 1):
            self.rejected("entry count")

    def test_unsafe_parent_and_blob_directory(self):
        blob = next(path for path in self.artifact.iterdir() if path.name != "manifest.json")
        blob.unlink()
        blob.mkdir()
        self.rejected("regular file")

    def test_symlink_parent_check_without_windows_symlink_privilege(self):
        original = Path.lstat
        parent = self.publisher / "docs"
        parent.mkdir(exist_ok=True)
        def hostile_lstat(path, *args, **kwargs):
            if path == parent:
                return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", hostile_lstat):
            self.rejected("Unsafe catalog parent")

    def test_symlink_blob_check_without_windows_symlink_privilege(self):
        original = Path.lstat
        blob = next(path for path in self.artifact.iterdir() if path.name != "manifest.json")
        def hostile_lstat(path, *args, **kwargs):
            if path == blob:
                return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", hostile_lstat):
            self.rejected("regular file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
