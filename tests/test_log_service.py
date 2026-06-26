import unittest

from proxy_checker.services.log_service import LogService


class FakeRuns:
    def __init__(self, items, on_clear=None):
        self._items = items
        self._on_clear = on_clear

    def list(self):
        return list(self._items)

    def clear(self):
        if self._on_clear:
            self._on_clear()


class FakeStorage:
    def __init__(self, runs):
        self.runs = runs


def make_factory(runs):
    return lambda _token: FakeStorage(runs)


class LogServiceTest(unittest.TestCase):
    def test_payload_adds_display_times(self):
        runs = FakeRuns([{"id": "one", "started_at": 1, "finished_at": 2, "timezone": "UTC"}])
        service = LogService(
            app_timezone="UTC",
            timezone_options=({"id": "UTC", "name": "UTC"},),
            storage_factory=make_factory(runs),
        )

        payload = service.payload("default")

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["logs"][0]["started_text"], "1970-01-01 00:00:01")
        self.assertEqual(payload["logs"][0]["finished_text"], "1970-01-01 00:00:02")
        self.assertEqual(payload["server_time"]["timezone"], "UTC")

    def test_clear_returns_empty_payload_after_clear(self):
        items = [{"id": "one", "started_at": 1}]

        def on_clear():
            items.clear()

        runs = FakeRuns(items, on_clear=on_clear)
        service = LogService(
            app_timezone="UTC",
            timezone_options=({"id": "UTC", "name": "UTC"},),
            storage_factory=make_factory(runs),
        )

        payload = service.clear("default")

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["logs"], [])


if __name__ == "__main__":
    unittest.main()
