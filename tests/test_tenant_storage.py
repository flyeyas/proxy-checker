import os
import tempfile
import unittest

from proxy_checker.storage.tenant import LegacyStorageLayout, TenantStorage, list_tenant_tokens


class TenantStorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.repo_dir = os.path.join(self.base, "repo_data")
        self.checked_dir = os.path.join(self.base, "checked_data")
        self.auto_dir = os.path.join(self.base, "auto_data")
        self.runs_dir = os.path.join(self.base, "logs")
        for path in (self.repo_dir, self.checked_dir, self.auto_dir, self.runs_dir):
            os.makedirs(path, exist_ok=True)
        self.layout = LegacyStorageLayout(
            repo_dir=self.repo_dir,
            checked_dir=self.checked_dir,
            auto_dir=self.auto_dir,
            runs_dir=self.runs_dir,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _storage(self, token):
        return TenantStorage(token, layout=self.layout)

    def test_repo_roundtrip(self):
        storage = self._storage("alpha")
        saved = storage.repo.write([{"proxy": "http://1.2.3.4:80", "grade": "A"}])
        self.assertEqual(len(saved), 1)
        self.assertEqual(storage.repo.read()[0]["proxy"], "http://1.2.3.4:80")
        self.assertTrue(os.path.isfile(storage.repo.json_path()))
        self.assertTrue(os.path.isfile(storage.repo.txt_path()))

    def test_repo_save_payload_merge(self):
        storage = self._storage("alpha")
        storage.repo.write([{"proxy": "http://1.1.1.1:80", "grade": "A"}])
        saved, response = storage.repo.save_payload(
            [{"proxy": "http://2.2.2.2:80", "grade": "B"}],
            mode="merge",
        )
        self.assertTrue(response["ok"])
        self.assertEqual(len(saved), 2)

    def test_checked_filter_unchecked(self):
        storage = self._storage("alpha")
        storage.checked.add(["http://1.1.1.1:80", "http://2.2.2.2:80"])
        unchecked = storage.checked.filter_unchecked(
            ["http://1.1.1.1:80", "http://3.3.3.3:80"]
        )
        self.assertEqual(unchecked, ["http://3.3.3.3:80"])
        self.assertEqual(storage.checked.count(), 2)

    def test_checked_stored_as_sqlite_db(self):
        storage = self._storage("alpha")
        storage.checked.add(["http://1.1.1.1:80"])
        self.assertTrue(storage.checked.path().endswith(".db"))
        self.assertTrue(os.path.isfile(storage.checked.path()))

    def test_checked_imports_legacy_txt_on_first_access(self):
        storage = self._storage("alpha")
        legacy_txt = storage.checked.path()[:-3] + ".txt"  # checked.db -> checked.txt
        os.makedirs(os.path.dirname(legacy_txt), exist_ok=True)
        with open(legacy_txt, "w", encoding="utf-8") as f:
            f.write("http://1.1.1.1:80\nhttp://2.2.2.2:80\n")
        fresh = TenantStorage("alpha", layout=self.layout)
        self.assertEqual(fresh.checked.count(), 2)
        self.assertTrue(fresh.checked.is_checked("http://1.1.1.1:80"))

    def test_auto_read_write(self):
        storage = self._storage("alpha")
        self.assertEqual(storage.auto.read(), {})
        storage.auto.write({"config": {"enabled": True}, "state": {"running": False}})
        self.assertEqual(storage.auto.read()["config"]["enabled"], True)

    def test_runs_insert_update_list_clear(self):
        storage = self._storage("alpha")
        run_id = storage.runs.insert({"id": "run_1", "type": "manual", "status": "running"})
        self.assertEqual(run_id, "run_1")
        storage.runs.update("run_1", {"status": "completed", "valid_count": 5})
        items = storage.runs.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "completed")
        self.assertEqual(items[0]["valid_count"], 5)
        storage.runs.clear()
        self.assertEqual(storage.runs.list(), [])

    def test_isolation_between_tokens(self):
        a = self._storage("alpha")
        b = self._storage("beta")
        a.repo.write([{"proxy": "http://1.1.1.1:80", "grade": "A"}])
        b.repo.write([{"proxy": "http://2.2.2.2:80", "grade": "B"}])
        self.assertEqual(len(a.repo.read()), 1)
        self.assertEqual(len(b.repo.read()), 1)
        self.assertNotEqual(a.repo.read()[0]["proxy"], b.repo.read()[0]["proxy"])

    def test_sanitize_token_applied(self):
        storage = self._storage("../weird token")
        self.assertEqual(storage.token, "default")

    def test_list_tenant_tokens_reads_auto_dir(self):
        a = self._storage("alpha")
        b = self._storage("beta")
        a.auto.write({"config": {}, "state": {}})
        b.auto.write({"config": {}, "state": {}})
        self.assertEqual(list_tenant_tokens(self.layout), ["alpha", "beta"])

    def _tenant_dir_storage(self, token):
        from proxy_checker.storage.tenant import TenantDirLayout

        data_dir = os.path.join(self.base, "data")
        return TenantStorage(token, layout=TenantDirLayout(data_dir=data_dir))

    def test_runs_stored_as_jsonl_one_line_per_entry(self):
        storage = self._tenant_dir_storage("alpha")
        storage.runs.insert({"id": "run_1", "type": "manual"})
        storage.runs.insert({"id": "run_2", "type": "auto"})
        path = storage.runs.path()
        self.assertTrue(path.endswith(".jsonl"))
        with open(path, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 2)

    def test_runs_migrates_legacy_json_on_first_access(self):
        import json

        from proxy_checker.storage.tenant import TenantDirLayout

        data_dir = os.path.join(self.base, "data")
        layout = TenantDirLayout(data_dir=data_dir)
        legacy_path = layout.runs_path("alpha")[:-1]  # runs.jsonl -> runs.json
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {"id": "old_1", "type": "manual", "started_at": 100},
                    {"id": "old_2", "type": "auto", "started_at": 200},
                ],
                f,
            )
        storage = TenantStorage("alpha", layout=layout)
        items = storage.runs.list()
        self.assertEqual([item["id"] for item in items], ["old_2", "old_1"])
        self.assertTrue(os.path.isfile(storage.runs.path()))

    def test_runs_list_caps_at_default_limit(self):
        storage = self._tenant_dir_storage("alpha")
        storage.runs.set_default_limit(20)
        for index in range(30):
            storage.runs.insert({"id": f"run_{index}", "started_at": index})
        self.assertEqual(len(storage.runs.list()), 20)


if __name__ == "__main__":
    unittest.main()
