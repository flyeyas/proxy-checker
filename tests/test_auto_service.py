import unittest

from proxy_checker.services.auto_service import AutoControlService


class AutoControlServiceTest(unittest.TestCase):
    def setUp(self):
        self.status_calls = []
        self.saved_configs = []
        self.started_runs = []
        self.stopped_tokens = []
        self.service = AutoControlService(
            get_status=self.get_status,
            save_config=self.save_config,
            start_run=self.start_run,
            stop_run=self.stop_run,
        )

    def get_status(self, token, since=0, session_id=""):
        self.status_calls.append((token, since, session_id))
        return {"token": token, "state": {"status": "idle"}}

    def save_config(self, token, config):
        self.saved_configs.append((token, config))
        return {"config": {"enabled": bool(config.get("enabled"))}, "state": {"status": "idle"}}

    def start_run(self, token, reason):
        self.started_runs.append((token, reason))
        return True, "run-id"

    def stop_run(self, token):
        self.stopped_tokens.append(token)
        return True

    def test_get_and_status_payloads(self):
        self.assertEqual(self.service.get_payload({"token": "demo", "since": 2, "session_id": "s"})["token"], "demo")
        self.assertEqual(self.service.status_payload({"token": "demo"})["token"], "demo")
        self.assertEqual(self.status_calls[0], ("demo", 2, "s"))

    def test_save_payload_includes_saved_record(self):
        payload = self.service.save_payload({"token": "demo", "config": {"enabled": True}})

        self.assertEqual(self.saved_configs, [("demo", {"enabled": True})])
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["config"], {"enabled": True})
        self.assertEqual(payload["state"], {"status": "idle"})

    def test_run_now_payload_marks_started(self):
        payload = self.service.run_now_payload({"token": "demo"})

        self.assertEqual(self.started_runs, [("demo", "manual")])
        self.assertTrue(payload["started"])
        self.assertNotIn("error", payload)

    def test_run_now_payload_includes_error_when_not_started(self):
        service = AutoControlService(
            get_status=self.get_status,
            save_config=self.save_config,
            start_run=lambda token, reason: (False, "busy"),
            stop_run=self.stop_run,
        )

        payload = service.run_now_payload({"token": "demo"})

        self.assertFalse(payload["started"])
        self.assertEqual(payload["error"], "busy")

    def test_stop_payload_marks_stopped(self):
        payload = self.service.stop_payload({"token": "demo", "since": 3, "session_id": "s"})

        self.assertEqual(self.stopped_tokens, ["demo"])
        self.assertTrue(payload["stopped"])
        self.assertEqual(self.status_calls[-1], ("demo", 3, "s"))


if __name__ == "__main__":
    unittest.main()
