import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from proxy_forge.services.check_service import ManualCheckService
from proxy_forge.services.runtime_check_service import create_manual_check_service


class RuntimeCheckServiceFactoryTest(unittest.TestCase):
    def test_create_manual_check_service_wires_runtime_dependencies(self):
        auto_runtime_store = Mock()
        runtime_options_service = FakeRuntimeOptionsService()
        state = SimpleNamespace(app_timezone="UTC", check_rounds=2, max_concurrent=30)

        service = create_manual_check_service(
            state=state,
            session_store=Mock(),
            auto_runtime_store=auto_runtime_store,
            check_engine_provider=lambda: "engine",
            runtime_options_service=runtime_options_service,
            logger=Mock(),
        )

        self.assertIsInstance(service, ManualCheckService)
        self.assertEqual(service.default_rounds(), 2)
        self.assertEqual(service.default_max_concurrent(), 30)
        self.assertEqual(service.app_timezone(), "UTC")
        service.is_auto_running("demo")
        auto_runtime_store.is_running.assert_called_once_with("demo")


class FakeRuntimeOptionsService:
    def normalize_rounds(self, value):
        return value

    def normalize_target_profile(self, value):
        return value or "generic"

    def normalize_max_concurrent(self, value):
        return value

    def get_target_profile_name(self, value):
        return value or "generic"


if __name__ == "__main__":
    unittest.main()
