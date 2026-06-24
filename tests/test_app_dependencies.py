import unittest
from unittest.mock import Mock

from proxy_checker.app_dependencies import AppDependencies, resolve_app_dependencies
from proxy_checker.services.log_service import LogService


class AppDependenciesTest(unittest.TestCase):
    def test_resolve_app_dependencies_preserves_custom_dependencies(self):
        custom = {
            "root_dir": "/tmp/app",
            "auth_service": Mock(),
            "settings_provider": Mock(),
            "capabilities_provider": Mock(),
            "server_time_provider": Mock(),
            "save_settings": Mock(),
            "start_check": Mock(),
            "get_check_status": Mock(),
            "stop_check": Mock(),
            "deep_check": Mock(),
            "fetch_proxies": Mock(),
            "get_auto": Mock(),
            "save_auto": Mock(),
            "run_auto_now": Mock(),
            "stop_auto": Mock(),
            "status_auto": Mock(),
            "log_service": Mock(),
            "repo_service": Mock(),
            "read_repo_data": Mock(),
            "save_repo_payload": Mock(),
            "write_repo_data": Mock(),
            "read_checked_list": Mock(),
            "write_checked_list": Mock(),
        }

        dependencies = resolve_app_dependencies(**custom)

        self.assertIsInstance(dependencies, AppDependencies)
        for key, value in custom.items():
            self.assertIs(getattr(dependencies, key), value)
        self.assertEqual(dependencies.blueprint_kwargs(), custom)

    def test_resolve_app_dependencies_fills_missing_runtime_handlers(self):
        dependencies = resolve_app_dependencies(
            root_dir="/tmp/app",
            auth_service=Mock(),
            settings_provider=lambda: {},
            capabilities_provider=lambda: {},
            server_time_provider=lambda: {},
        )

        self.assertIsInstance(dependencies.log_service, LogService)
        self.assertIn("尚未接入", dependencies.start_check({})["error"])
        self.assertIn("尚未接入", dependencies.status_auto({})["error"])
        self.assertFalse(dependencies.deep_check({})["success"])

    def test_resolve_app_dependencies_allows_disabling_deep_check(self):
        dependencies = resolve_app_dependencies(
            root_dir="/tmp/app",
            auth_service=Mock(),
            settings_provider=lambda: {},
            capabilities_provider=lambda: {},
            server_time_provider=lambda: {},
            deep_check=None,
        )

        self.assertIsNone(dependencies.deep_check)


if __name__ == "__main__":
    unittest.main()
