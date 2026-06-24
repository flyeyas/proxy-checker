import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from proxy_checker.services.runtime_lifecycle_service import RuntimeLifecycleService


class RuntimeLifecycleServiceTest(unittest.TestCase):
    def test_start_background_services_starts_components_and_logs_runtime_status(self):
        session_cleanup_service = Mock()
        auto_coordinator_service = Mock()
        gateway_runtime_service = Mock()
        logger = Mock()
        service = RuntimeLifecycleService(
            state=SimpleNamespace(max_concurrent=30, check_rounds=2),
            session_cleanup_service=session_cleanup_service,
            auto_coordinator_service=auto_coordinator_service,
            gateway_runtime_service=gateway_runtime_service,
            deep_check_service=SimpleNamespace(available=True),
            logger=logger,
        )

        service.start_background_services()

        session_cleanup_service.start.assert_called_once_with()
        auto_coordinator_service.start_scheduler.assert_called_once_with()
        gateway_runtime_service.start.assert_called_once_with()
        logger.info.assert_any_call("Deep check (nodriver): available")
        logger.info.assert_any_call("Concurrency: 30 | Rounds: 2")
        logger.info.assert_any_call("Auto mode scheduler started")


if __name__ == "__main__":
    unittest.main()
