import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from proxy_checker.services.auto_coordinator_service import AutoRunCoordinator
from proxy_checker.services.auto_record_service import AutoRecordService
from proxy_checker.services.auto_runtime_service import AutoRuntimeStore
from proxy_checker.services.auto_service import AutoControlService
from proxy_checker.services.runtime_auto_service import create_runtime_auto_services


class RuntimeAutoServiceFactoryTest(unittest.TestCase):
    def test_create_runtime_auto_services_wires_shared_runtime_dependencies(self):
        runtime_options_service = FakeRuntimeOptionsService()
        repo_update_service = SimpleNamespace(merge_repo_results=Mock(return_value={}))

        services = create_runtime_auto_services(
            state=SimpleNamespace(check_rounds=2, max_concurrent=30, app_timezone="UTC"),
            runtime_options_service=runtime_options_service,
            fetch_service=Mock(),
            check_engine_provider=lambda: "engine",
            repo_update_service=repo_update_service,
            logger=Mock(),
        )

        self.assertIsInstance(services.runtime_store, AutoRuntimeStore)
        self.assertIsInstance(services.record_service, AutoRecordService)
        self.assertIsInstance(services.coordinator_service, AutoRunCoordinator)
        self.assertIsInstance(services.control_service, AutoControlService)
        self.assertIs(services.coordinator_service.runtime_store, services.runtime_store)
        self.assertIs(services.coordinator_service.record_service, services.record_service)
        self.assertIs(services.coordinator_service.merge_repo_results, repo_update_service.merge_repo_results)
        self.assertEqual(services.coordinator_service.default_rounds(), 2)
        self.assertEqual(services.coordinator_service.default_max_concurrent(), 30)
        self.assertEqual(services.coordinator_service.default_timezone(), "UTC")


class FakeRuntimeOptionsService:
    def normalize_auto_config(self, config):
        return config or {}

    def default_auto_state(self, _config=None):
        return {}

    def compute_next_run(self, _config, now=None):
        return now

    def format_timestamp(self, timestamp, timezone_id=None):
        return f"{timezone_id}:{timestamp}"

    def server_time_payload(self, timezone_id=None):
        return {"timezone": timezone_id}

    def get_target_profile_name(self, value):
        return value or "generic"


if __name__ == "__main__":
    unittest.main()
