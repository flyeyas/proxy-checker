import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from proxy_checker.services.runtime_settings_payload_service import RuntimeSettingsPayloadService


class RuntimeSettingsPayloadServiceTest(unittest.TestCase):
    def test_public_settings_uses_dynamic_state_and_gateway(self):
        state = runtime_state()
        gateway = FakeGatewayService()
        service = RuntimeSettingsPayloadService(
            state=state,
            proxy_gateway_service=gateway,
            timezone_options=({"id": "UTC", "name": "UTC"},),
        )

        with patch.dict(os.environ, {}, clear=True):
            payload = service.public_settings()

        self.assertEqual(payload["check_rounds"], 2)
        self.assertEqual(payload["max_concurrent"], 30)
        self.assertEqual(payload["timezone_options"], [{"id": "UTC", "name": "UTC"}])
        self.assertEqual(payload["password_configurable"], True)
        self.assertEqual(payload["proxy_gateway"], {
            "enabled": True,
            "bind": "127.0.0.1",
            "port": 7890,
            "grades": ["A", "B"],
            "token": "gateway-token",
        })

        state.check_rounds = 3
        state.max_concurrent = 50
        with patch.dict(os.environ, {"AUTH_PASSWORD": "locked"}, clear=True):
            payload = service.public_settings()

        self.assertEqual(payload["check_rounds"], 3)
        self.assertEqual(payload["max_concurrent"], 50)
        self.assertEqual(payload["password_configurable"], False)

    def test_runtime_config_uses_dynamic_state(self):
        state = runtime_state()
        service = RuntimeSettingsPayloadService(state=state, proxy_gateway_service=FakeGatewayService())

        state.timeout = 45
        state.app_timezone = "Asia/Shanghai"
        payload = service.runtime_config()

        self.assertEqual(payload["timeout"], 45)
        self.assertEqual(payload["timezone"], "Asia/Shanghai")
        self.assertNotIn("proxy_gateway", payload)


def runtime_state():
    return SimpleNamespace(
        check_rounds=2,
        max_check_rounds=5,
        max_concurrent=30,
        max_concurrent_limit=100,
        timeout=12,
        detect_timeout=8,
        auth_session_days=7,
        log_limit=100,
        app_timezone="UTC",
        port=8888,
        proxy_gateway_enabled=True,
        proxy_gateway_bind="127.0.0.1",
        proxy_gateway_port=7890,
    )


class FakeGatewayService:
    token = "gateway-token"

    def allowed_grades(self):
        return {"B", "A"}


if __name__ == "__main__":
    unittest.main()
