import unittest

from proxy_checker.services.log_service import LogService


class LogServiceTest(unittest.TestCase):
    def test_payload_adds_display_times(self):
        service = LogService(
            app_timezone="UTC",
            timezone_options=({"id": "UTC", "name": "UTC"},),
            read_logs_func=lambda _token: [{"id": "one", "started_at": 1, "finished_at": 2, "timezone": "UTC"}],
            clear_logs_func=lambda _token: None,
        )

        payload = service.payload("default")

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["logs"][0]["started_text"], "1970-01-01 00:00:01")
        self.assertEqual(payload["logs"][0]["finished_text"], "1970-01-01 00:00:02")
        self.assertEqual(payload["server_time"]["timezone"], "UTC")

    def test_clear_returns_empty_payload_after_clear(self):
        logs = [{"id": "one", "started_at": 1}]

        def read_logs(_token):
            return list(logs)

        def clear_logs(_token):
            logs.clear()

        service = LogService(
            app_timezone="UTC",
            timezone_options=({"id": "UTC", "name": "UTC"},),
            read_logs_func=read_logs,
            clear_logs_func=clear_logs,
        )

        payload = service.clear("default")

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["logs"], [])


if __name__ == "__main__":
    unittest.main()
