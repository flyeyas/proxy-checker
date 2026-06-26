import threading
import unittest

from proxy_checker.services.auto_coordinator_service import AutoRunCoordinator
from proxy_checker.services.auto_runtime_service import AutoRuntimeStore
from proxy_checker.services.auto_run_service import build_auto_runtime


class AutoRunCoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.runtime_store = AutoRuntimeStore()
        self.record_service = FakeRecordService(self.config())
        self.fetch_service = FakeFetchService(["http://1.1.1.1:80", "http://2.2.2.2:80"])
        self.engine = FakeCheckEngine()
        self.storage = FakeStorage(
            repo=[{"proxy": "http://2.2.2.2:80"}, {"proxy": "http://3.3.3.3:80"}],
            checked=["http://3.3.3.3:80"],
        )
        self.merged_calls = []
        self.coordinator = AutoRunCoordinator(
            runtime_store=self.runtime_store,
            record_service=self.record_service,
            fetch_service=self.fetch_service,
            check_engine_provider=lambda: self.engine,
            normalize_config=lambda config: {**self.config(), **(config or {})},
            compute_next_run=lambda _config, _now=None: 1234,
            target_name=lambda profile: f"Target {profile}",
            storage_factory=lambda _token: self.storage,
            merge_repo_results=self.merge_repo_results,
            list_tokens=lambda: ["demo"],
            default_rounds=lambda: 2,
            default_max_concurrent=lambda: 5,
            default_timezone=lambda: "UTC",
        )

    @staticmethod
    def config():
        return {
            "enabled": True,
            "schedule_type": "interval",
            "interval_hours": 6,
            "daily_time": "03:00",
            "timezone": "UTC",
            "target_profile": "generic",
            "rounds": 2,
            "max_concurrent": 5,
            "detect_mode": "skip",
            "repo_update_policy": "stable_only",
        }

    def merge_repo_results(self, **kwargs):
        self.merged_calls.append(kwargs)
        return {"repo_added_count": 1}

    def test_execute_run_completes_and_merges_results(self):
        config = self.config()
        runtime = build_auto_runtime("run-id", "log-id", "manual", 100, config, threading.Event())
        self.runtime_store.create("demo", runtime)

        self.coordinator.execute_run("demo", config, "run-id", "manual")

        self.assertFalse(self.runtime_store.has("demo"))
        self.assertEqual(self.engine.checked_proxies, ["http://1.1.1.1:80", "http://2.2.2.2:80"])
        self.assertEqual(self.storage.checked.added, [["http://1.1.1.1:80", "http://2.2.2.2:80"]])
        self.assertEqual(self.merged_calls[0]["checked_inputs"], ["http://1.1.1.1:80", "http://2.2.2.2:80"])
        finished = self.storage.runs.updated[-1]
        self.assertEqual(finished[1]["status"], "completed")
        self.assertEqual(self.record_service.records["demo"]["state"]["status"], "completed")
        self.assertEqual(self.record_service.records["demo"]["state"]["last_summary"]["repo_added_count"], 1)

    def test_stop_run_sets_runtime_and_persisted_state(self):
        config = self.config()
        runtime = build_auto_runtime("run-id", "log-id", "manual", 100, config, threading.Event())
        self.runtime_store.create("demo", runtime)

        stopped = self.coordinator.stop_run("demo")

        self.assertTrue(stopped)
        self.assertTrue(runtime["stop"].is_set())
        self.assertEqual(self.record_service.records["demo"]["state"]["status"], "stopping")


class FakeRecordService:
    def __init__(self, config):
        self.records = {
            "demo": {
                "config": dict(config),
                "state": {
                    "running": False,
                    "status": "idle",
                    "history": [],
                },
            }
        }

    def load(self, token):
        record = self.records.setdefault(token, {"config": {}, "state": {"history": []}})
        return {
            "config": dict(record["config"]),
            "state": {
                **record["state"],
                "history": list(record["state"].get("history", [])),
            },
        }

    def save(self, token, record):
        self.records[token] = {
            "config": dict(record["config"]),
            "state": {
                **record["state"],
                "history": list(record["state"].get("history", [])),
            },
        }
        return self.load(token)

    def append_history(self, state, summary):
        history = state.get("history") if isinstance(state.get("history"), list) else []
        history.append(summary)
        state["history"] = history[-20:]
        state["last_summary"] = summary

    def status_payload(self, token, runtime=None, stopped=None, since=0, client_session_id=""):
        payload = self.load(token)
        payload.update({
            "runtime": bool(runtime),
            "stopped": bool(stopped),
            "since": since,
            "session_id": client_session_id,
        })
        return payload


class FakeFetchService:
    available = True

    def __init__(self, proxies):
        self.proxies = proxies

    def fetch(self, source, limit):
        return list(self.proxies[:limit]), source, None


class FakeCheckEngine:
    def __init__(self):
        self.checked_proxies = []

    async def check_many_async(self, **kwargs):
        self.checked_proxies = list(kwargs["proxies"])
        for proxy in self.checked_proxies:
            kwargs["on_result"]({"proxy": proxy, "original": proxy, "valid": True})


class FakeRepoBackend:
    def __init__(self, items):
        self._items = list(items)

    def read(self):
        return list(self._items)


class FakeCheckedBackend:
    def __init__(self, items):
        self._items = list(items)
        self.added = []

    def filter_unchecked(self, proxies):
        existing = set(self._items)
        return [p for p in proxies if p not in existing]

    def add(self, proxies):
        proxies = list(proxies)
        self.added.append(proxies)
        for p in proxies:
            if p not in self._items:
                self._items.append(p)


class FakeRunsBackend:
    def __init__(self):
        self.inserted = []
        self.updated = []

    def insert(self, entry):
        self.inserted.append(dict(entry))
        return "log-id"

    def update(self, run_id, fields):
        self.updated.append((run_id, dict(fields)))


class FakeStorage:
    def __init__(self, repo, checked):
        self.repo = FakeRepoBackend(repo)
        self.checked = FakeCheckedBackend(checked)
        self.runs = FakeRunsBackend()


if __name__ == "__main__":
    unittest.main()
