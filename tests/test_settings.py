import importlib
import unittest
from unittest.mock import patch

from proxy_checker import config
from proxy_checker.config import CHECK_ROUNDS, PORT, Settings


class SettingsTest(unittest.TestCase):
    def test_config_import_does_not_create_runtime_dirs(self):
        with patch("os.makedirs") as make_dirs:
            importlib.reload(config)

        make_dirs.assert_not_called()

    def test_load_reads_runtime_defaults(self):
        state = Settings.load()

        self.assertEqual(state.port, PORT)
        self.assertEqual(state.check_rounds, CHECK_ROUNDS)
        self.assertGreaterEqual(state.http_threads, 1)

    def test_settings_context_and_apply_resolved_settings(self):
        state = Settings.load()
        context = state.settings_context()

        self.assertEqual(context["timeout"], state.timeout)
        self.assertEqual(context["auth_session_secret"], state.auth_session_secret)

        resolved = dict(context)
        resolved.update({
            "timeout": 30,
            "detect_timeout": 15,
            "max_concurrent": 40,
            "max_concurrent_limit": 80,
            "check_rounds": 3,
            "max_check_rounds": 5,
            "log_limit": 200,
            "auth_password": "new-password",
            "auth_session_days": 10,
            "auth_session_seconds": 864000,
            "auth_session_secret": "new-secret",
            "app_timezone": "Asia/Shanghai",
        })

        state.apply_resolved_settings(resolved)

        self.assertEqual(state.timeout, 30)
        self.assertEqual(state.max_concurrent, 40)
        self.assertEqual(state.auth_password, "new-password")
        self.assertEqual(state.app_timezone, "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
