import io
import json
import logging
import os
import tempfile
import unittest

from proxy_forge.migrate import v1_to_v2


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_json(path, data):
    _write_text(path, json.dumps(data))


class MigrateV1ToV2Test(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.base = base
        self.data_dir = os.path.join(base, "data")
        self.repo_dir = os.path.join(base, "repo_data")
        self.checked_dir = os.path.join(base, "checked_data")
        self.auto_dir = os.path.join(base, "auto_data")
        self.runs_dir = os.path.join(base, "logs")
        self._dirs = dict(
            data_dir=self.data_dir,
            repo_dir=self.repo_dir,
            checked_dir=self.checked_dir,
            auto_dir=self.auto_dir,
            runs_dir=self.runs_dir,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_full_tenant(self, token):
        _write_json(
            os.path.join(self.repo_dir, f"{token}.json"),
            [{"proxy": "http://1.1.1.1:80", "grade": "A"}],
        )
        _write_text(os.path.join(self.repo_dir, f"{token}.txt"), "http://1.1.1.1:80")
        _write_text(
            os.path.join(self.checked_dir, f"{token}.txt"),
            "http://1.1.1.1:80\nhttp://2.2.2.2:80",
        )
        _write_json(
            os.path.join(self.auto_dir, f"{token}.json"),
            {"config": {"enabled": True}, "state": {"running": False}},
        )
        _write_json(
            os.path.join(self.runs_dir, f"{token}.json"),
            [{"id": "run_1", "type": "manual", "status": "completed", "started_at": 1}],
        )

    def test_list_legacy_tokens_dedups(self):
        self._seed_full_tenant("alpha")
        _write_json(os.path.join(self.repo_dir, "beta.json"), [])
        tokens = v1_to_v2.list_legacy_tokens(**{k: v for k, v in self._dirs.items() if k != "data_dir"})
        self.assertEqual(tokens, ["alpha", "beta"])

    def test_list_legacy_tokens_rejects_unsafe_names(self):
        _write_json(os.path.join(self.repo_dir, "../escape.json"), [])
        _write_json(os.path.join(self.repo_dir, "with space.json"), [])
        _write_json(os.path.join(self.repo_dir, "good_one.json"), [])
        tokens = v1_to_v2.list_legacy_tokens(**{k: v for k, v in self._dirs.items() if k != "data_dir"})
        self.assertEqual(tokens, ["good_one"])

    def test_migrate_full_tenant_copies_all_files(self):
        self._seed_full_tenant("alpha")
        status = v1_to_v2.migrate_tenant("alpha", **self._dirs)
        self.assertEqual(status, "migrated")
        new_dir = os.path.join(self.data_dir, "alpha")
        for name in ("repo.json", "repo.txt", "checked.txt", "auto.json", "runs.json"):
            self.assertTrue(os.path.isfile(os.path.join(new_dir, name)), name)
        self.assertTrue(os.path.isfile(os.path.join(self.repo_dir, "alpha.json")))

    def test_migrate_partial_tenant_is_ok(self):
        _write_json(
            os.path.join(self.auto_dir, "alpha.json"),
            {"config": {}, "state": {}},
        )
        status = v1_to_v2.migrate_tenant("alpha", **self._dirs)
        self.assertEqual(status, "migrated")
        new_dir = os.path.join(self.data_dir, "alpha")
        self.assertTrue(os.path.isfile(os.path.join(new_dir, "auto.json")))
        self.assertFalse(os.path.isfile(os.path.join(new_dir, "repo.json")))

    def test_migrate_no_legacy_skips_directory_creation(self):
        status = v1_to_v2.migrate_tenant("ghost", **self._dirs)
        self.assertEqual(status, "no_legacy")
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "ghost")))

    def test_migrate_invalid_token_rejected(self):
        status = v1_to_v2.migrate_tenant("../weird", **self._dirs)
        self.assertEqual(status, "invalid_token")
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "..")))

    def test_migrate_idempotent(self):
        self._seed_full_tenant("alpha")
        first = v1_to_v2.run(**self._dirs)
        second = v1_to_v2.run(**self._dirs)
        self.assertEqual(first, {"alpha": "migrated"})
        self.assertEqual(second, {"alpha": "skipped"})

    def test_dry_run_writes_nothing(self):
        self._seed_full_tenant("alpha")
        results = v1_to_v2.run(dry_run=True, **self._dirs)
        self.assertEqual(results, {"alpha": "would_migrate"})
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "alpha")))

    def test_needs_migration_detects_pending_tokens(self):
        self.assertFalse(v1_to_v2.needs_migration(**self._dirs))
        self._seed_full_tenant("alpha")
        self.assertTrue(v1_to_v2.needs_migration(**self._dirs))
        v1_to_v2.run(**self._dirs)
        self.assertFalse(v1_to_v2.needs_migration(**self._dirs))

    def test_purge_legacy_removes_only_expected_paths(self):
        self._seed_full_tenant("alpha")
        _write_text(os.path.join(self.runs_dir, "server.log"), "log line\n")
        v1_to_v2.run(**self._dirs)
        removed = v1_to_v2.purge_legacy(
            repo_dir=self.repo_dir,
            checked_dir=self.checked_dir,
            auto_dir=self.auto_dir,
            runs_dir=self.runs_dir,
        )
        self.assertFalse(os.path.isdir(self.repo_dir))
        self.assertFalse(os.path.isdir(self.checked_dir))
        self.assertFalse(os.path.isdir(self.auto_dir))
        self.assertTrue(os.path.isfile(os.path.join(self.runs_dir, "server.log")))
        self.assertFalse(os.path.isfile(os.path.join(self.runs_dir, "alpha.json")))
        self.assertIn(self.repo_dir, removed)

    def test_maybe_run_migration_logs_and_runs(self):
        self._seed_full_tenant("alpha")
        logger = logging.getLogger("migrate_test_logger")
        logger.handlers = []
        logger.setLevel(logging.INFO)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        results = v1_to_v2.maybe_run_migration(logger=logger, **self._dirs)
        self.assertEqual(results, {"alpha": "migrated"})
        output = stream.getvalue()
        self.assertIn("legacy storage", output)
        self.assertIn("completed", output)

    def test_maybe_run_migration_no_op_when_nothing_legacy(self):
        result = v1_to_v2.maybe_run_migration(**self._dirs)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
