import unittest

from proxy_checker.services.session_cleanup_service import SessionCleanupService


class SessionCleanupServiceTest(unittest.TestCase):
    def test_cleanup_once_delegates_to_store_and_logs_removed_sessions(self):
        logger = FakeLogger()
        store = FakeSessionStore((2, 3))
        service = SessionCleanupService(store, max_age_seconds=60, interval_seconds=1, logger=logger)

        removed, remaining = service.cleanup_once()

        self.assertEqual((removed, remaining), (2, 3))
        self.assertEqual(store.max_age_seconds, 60)
        self.assertEqual(logger.messages, ["Cleaned up 2 stale sessions, 3 remaining"])

    def test_cleanup_once_skips_log_when_nothing_removed(self):
        logger = FakeLogger()
        service = SessionCleanupService(FakeSessionStore((0, 5)), logger=logger)

        service.cleanup_once()

        self.assertEqual(logger.messages, [])


class FakeSessionStore:
    def __init__(self, result):
        self.result = result
        self.max_age_seconds = None

    def cleanup_finished(self, max_age_seconds):
        self.max_age_seconds = max_age_seconds
        return self.result


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)


if __name__ == "__main__":
    unittest.main()
