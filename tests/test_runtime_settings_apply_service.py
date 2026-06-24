import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from proxy_checker.services.runtime_settings_apply_service import (
    RuntimeCheckEngineFactory,
    RuntimeSettingsApplyService,
)


class RuntimeCheckEngineFactoryTest(unittest.TestCase):
    def test_create_uses_current_state(self):
        state = FakeRuntimeState()
        factory = RuntimeCheckEngineFactory(state)

        engine = factory.create()

        self.assertEqual(engine.config.timeout, 12)
        self.assertEqual(engine.config.detect_timeout, 8)
        self.assertEqual(engine.config.check_rounds, 2)


class RuntimeSettingsApplyServiceTest(unittest.TestCase):
    def test_apply_updates_state_auth_log_limit_and_engine(self):
        state = FakeRuntimeState()
        auth_service = Mock()
        log_limits = []
        service = RuntimeSettingsApplyService(
            state=state,
            runtime_options_service=SimpleNamespace(normalize_timezone=lambda value: value),
            auth_service=auth_service,
            check_engine_factory=RuntimeCheckEngineFactory(state),
            environ={},
            set_log_limit_func=log_limits.append,
        )

        password_changed, engine = service.apply({
            "timeout": 30,
            "detect_timeout": 15,
            "check_rounds": 3,
            "max_check_rounds": 5,
            "log_limit": 250,
            "auth_password": "new-secret",
            "timezone": "Asia/Shanghai",
        })

        self.assertTrue(password_changed)
        self.assertEqual(state.timeout, 30)
        self.assertEqual(state.detect_timeout, 15)
        self.assertEqual(state.check_rounds, 3)
        self.assertEqual(state.log_limit, 250)
        self.assertEqual(state.auth_password, "new-secret")
        self.assertEqual(state.auth_session_secret, "new-secret")
        self.assertEqual(state.app_timezone, "Asia/Shanghai")
        self.assertEqual(log_limits, [250])
        auth_service.configure.assert_called_once_with("new-secret", "new-secret", state.auth_session_seconds)
        self.assertEqual(engine.config.timeout, 30)
        self.assertEqual(engine.config.check_rounds, 3)

    def test_apply_respects_password_env_lock(self):
        state = FakeRuntimeState()
        auth_service = Mock()
        service = RuntimeSettingsApplyService(
            state=state,
            runtime_options_service=SimpleNamespace(normalize_timezone=lambda value: value),
            auth_service=auth_service,
            check_engine_factory=RuntimeCheckEngineFactory(state),
            environ={"AUTH_PASSWORD": "locked"},
            set_log_limit_func=lambda _value: None,
        )

        password_changed, _engine = service.apply({"auth_password": "new-secret"})

        self.assertFalse(password_changed)
        self.assertEqual(state.auth_password, "old-secret")
        self.assertEqual(state.auth_session_secret, "old-session-secret")


class FakeRuntimeState:
    def __init__(self):
        self.timeout = 12
        self.detect_timeout = 8
        self.max_concurrent = 30
        self.max_concurrent_limit = 100
        self.check_rounds = 2
        self.max_check_rounds = 3
        self.log_limit = 100
        self.auth_password = "old-secret"
        self.auth_session_days = 7
        self.auth_session_seconds = 7 * 86400
        self.auth_session_secret = "old-session-secret"
        self.app_timezone = "UTC"

    def settings_context(self):
        return {
            "timeout": self.timeout,
            "detect_timeout": self.detect_timeout,
            "max_concurrent": self.max_concurrent,
            "max_concurrent_limit": self.max_concurrent_limit,
            "check_rounds": self.check_rounds,
            "max_check_rounds": self.max_check_rounds,
            "log_limit": self.log_limit,
            "auth_password": self.auth_password,
            "auth_session_days": self.auth_session_days,
            "auth_session_seconds": self.auth_session_seconds,
            "auth_session_secret": self.auth_session_secret,
            "app_timezone": self.app_timezone,
        }

    def apply_resolved_settings(self, resolved):
        self.timeout = resolved["timeout"]
        self.detect_timeout = resolved["detect_timeout"]
        self.max_concurrent = resolved["max_concurrent"]
        self.max_concurrent_limit = resolved["max_concurrent_limit"]
        self.check_rounds = resolved["check_rounds"]
        self.max_check_rounds = resolved["max_check_rounds"]
        self.log_limit = resolved["log_limit"]
        self.auth_password = resolved["auth_password"]
        self.auth_session_days = resolved["auth_session_days"]
        self.auth_session_seconds = resolved["auth_session_seconds"]
        self.auth_session_secret = resolved["auth_session_secret"]
        self.app_timezone = resolved["app_timezone"]


if __name__ == "__main__":
    unittest.main()
