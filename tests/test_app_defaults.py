import unittest

from proxy_forge.app_defaults import (
    create_default_auto_handlers,
    create_default_check_handlers,
    create_default_deep_check_handler,
)


class AppDefaultsTest(unittest.TestCase):
    def test_default_check_handlers_return_unsupported_payload(self):
        start_check, get_status, stop_check = create_default_check_handlers()

        self.assertIn("尚未接入", start_check({})["error"])
        self.assertIn("尚未接入", get_status({})["error"])
        self.assertIn("尚未接入", stop_check({})["error"])

    def test_default_auto_handlers_return_unsupported_payload(self):
        for handler in create_default_auto_handlers():
            self.assertIn("尚未接入", handler({})["error"])

    def test_default_deep_check_handler_returns_install_hint(self):
        payload = create_default_deep_check_handler()({})

        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "nodriver not installed")
        self.assertIn("nodriver", payload["hint"])


if __name__ == "__main__":
    unittest.main()
