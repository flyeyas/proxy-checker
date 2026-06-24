import unittest

from proxy_checker.services.check_service import ManualCheckService
from proxy_checker.services.session_service import InMemorySessionStore


class ManualCheckServiceTest(unittest.TestCase):
    def setUp(self):
        self.session_store = InMemorySessionStore()
        self.started_logs = []
        self.finished_logs = []
        self.engine = FakeCheckEngine()
        self.service = ManualCheckService(
            session_store=self.session_store,
            check_engine=self.engine,
            normalize_rounds=lambda value: int(value or 2),
            normalize_target_profile=lambda value: value or "generic",
            normalize_max_concurrent=lambda value: int(value or 30),
            target_name=lambda value: f"Target {value}",
            is_auto_running=lambda _token: False,
            start_log=self.start_log,
            finish_log=self.finish_log,
            count_results=self.count_results,
            app_timezone="UTC",
            default_rounds=2,
            default_max_concurrent=30,
        )

    def start_log(self, token, entry):
        self.started_logs.append((token, entry))
        return "log-id"

    def finish_log(self, token, log_id, updates):
        self.finished_logs.append((token, log_id, updates))

    @staticmethod
    def count_results(results):
        valid = sum(1 for result in results if result.get("valid"))
        unstable = sum(1 for result in results if result.get("unstable"))
        invalid = len(results) - valid - unstable
        return valid, unstable, invalid

    def test_start_payload_creates_session_and_log(self):
        payload = self.service.start_payload({
            "proxies": ["http://127.0.0.1:8080"],
            "rounds": 1,
            "target_profile": "generic",
            "max_concurrent": 5,
            "token": "demo",
        })

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["rounds"], 1)
        self.assertEqual(payload["target_profile"], "generic")
        self.assertEqual(payload["max_concurrent"], 5)
        self.assertEqual(self.started_logs[0][0], "demo")

    def test_status_and_stop_payloads(self):
        self.session_store.create("session", total=1, max_concurrent=5)

        status = self.service.status_payload({"session_id": "session", "since": 0})
        stop = self.service.stop_payload({"session_id": "session"})

        self.assertEqual(status["total"], 1)
        self.assertEqual(status["max_concurrent"], 5)
        self.assertEqual(stop, {"ok": True})

    def test_run_check_finishes_session_and_log(self):
        self.session_store.create("session", total=2, token="demo", log_id="log-id")

        self.service.run_check("session", ["a", "b"], rounds=1, target_profile="generic", max_concurrent=2, token="demo")

        self.assertEqual(self.engine.calls[0]["proxies"], ["a", "b"])
        self.assertEqual(len(self.finished_logs), 1)
        token, log_id, updates = self.finished_logs[0]
        self.assertEqual(token, "demo")
        self.assertEqual(log_id, "log-id")
        self.assertEqual(updates["status"], "completed")
        self.assertEqual(updates["valid_count"], 1)
        self.assertEqual(updates["invalid_count"], 1)

    def test_auto_running_blocks_manual_start(self):
        service = ManualCheckService(
            session_store=self.session_store,
            check_engine=self.engine,
            normalize_rounds=lambda value: 1,
            normalize_target_profile=lambda value: "generic",
            normalize_max_concurrent=lambda value: 1,
            target_name=lambda value: value,
            is_auto_running=lambda _token: True,
            start_log=self.start_log,
            finish_log=self.finish_log,
            count_results=self.count_results,
            app_timezone="UTC",
            default_rounds=1,
            default_max_concurrent=1,
        )

        payload = service.start_payload({"proxies": ["a"], "token": "demo"})

        self.assertEqual(payload["auto_running"], True)
        self.assertEqual(self.started_logs, [])

    def test_run_check_uses_current_engine_provider(self):
        first_engine = FakeCheckEngine()
        second_engine = FakeCheckEngine()
        current = {"engine": first_engine}
        service = ManualCheckService(
            session_store=self.session_store,
            check_engine_provider=lambda: current["engine"],
            normalize_rounds=lambda value: 1,
            normalize_target_profile=lambda value: "generic",
            normalize_max_concurrent=lambda value: 1,
            target_name=lambda value: value,
            is_auto_running=lambda _token: False,
            start_log=self.start_log,
            finish_log=self.finish_log,
            count_results=self.count_results,
            app_timezone="UTC",
            default_rounds=1,
            default_max_concurrent=1,
        )
        self.session_store.create("session", total=1, token="demo", log_id="log-id")

        current["engine"] = second_engine
        service.run_check("session", ["a"], rounds=1, target_profile="generic", max_concurrent=1, token="demo")

        self.assertEqual(first_engine.calls, [])
        self.assertEqual(second_engine.calls[0]["proxies"], ["a"])

    def test_run_check_uses_current_default_settings(self):
        current = {"rounds": 2, "max_concurrent": 4}
        service = ManualCheckService(
            session_store=self.session_store,
            check_engine=self.engine,
            normalize_rounds=lambda value: int(value),
            normalize_target_profile=lambda value: value or "generic",
            normalize_max_concurrent=lambda value: int(value),
            target_name=lambda value: value,
            is_auto_running=lambda _token: False,
            start_log=self.start_log,
            finish_log=self.finish_log,
            count_results=self.count_results,
            app_timezone=lambda: "UTC",
            default_rounds=lambda: current["rounds"],
            default_max_concurrent=lambda: current["max_concurrent"],
        )
        self.session_store.create("session", total=1, token="demo", log_id="log-id")

        current.update({"rounds": 3, "max_concurrent": 7})
        service.run_check("session", ["a"], token="demo")

        self.assertEqual(self.engine.calls[0]["rounds"], 3)
        self.assertEqual(self.engine.calls[0]["max_concurrent"], 7)


class FakeCheckEngine:
    def __init__(self):
        self.calls = []

    async def check_many_async(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["on_result"]({"proxy": "a", "valid": True})
        kwargs["on_result"]({"proxy": "b", "valid": False})


if __name__ == "__main__":
    unittest.main()
