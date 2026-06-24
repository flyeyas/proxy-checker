import unittest

from proxy_checker.services.runtime_settings_service import (
    RuntimeCapabilitiesService,
    RuntimeSettingsService,
    create_runtime_capabilities_service,
    create_runtime_settings_service,
    resolve_runtime_settings,
)
from proxy_checker.storage.config_store import read_local_config, write_local_config


class RuntimeSettingsServiceTest(unittest.TestCase):
    def test_save_payload_persists_runtime_config_without_password_change(self):
        writes = []
        service = RuntimeSettingsService(
            apply_runtime_settings=lambda settings: False,
            read_local_config=lambda: {"old": True},
            write_local_config=lambda config: writes.append(config),
            runtime_config=lambda: {"check_rounds": 2},
            public_settings=lambda: {"check_rounds": 2},
            auth_password=lambda: "new-secret",
            make_auth_token=lambda: "token",
            session_seconds=lambda: 60,
        )

        payload = service.save_payload({"check_rounds": 2})

        self.assertEqual(writes, [{"old": True, "check_rounds": 2}])
        self.assertEqual(payload, {
            "ok": True,
            "settings": {"check_rounds": 2},
            "password_changed": False,
        })

    def test_save_payload_includes_new_token_when_password_changes(self):
        writes = []
        service = RuntimeSettingsService(
            apply_runtime_settings=lambda settings: True,
            read_local_config=lambda: {},
            write_local_config=lambda config: writes.append(config),
            runtime_config=lambda: {"check_rounds": 3},
            public_settings=lambda: {"check_rounds": 3},
            auth_password=lambda: "new-secret",
            make_auth_token=lambda: "token",
            session_seconds=lambda: 120,
        )

        payload = service.save_payload({"auth_password": "new-secret"})

        self.assertEqual(writes, [{"check_rounds": 3, "auth_password": "new-secret"}])
        self.assertEqual(payload["token"], "token")
        self.assertEqual(payload["expires_in"], 120)
        self.assertTrue(payload["password_changed"])

    def test_create_runtime_settings_service_wires_runtime_dependencies(self):
        state = FakeSettingsState()
        auth_service = SimpleAuthService()
        settings_payload_service = SimpleSettingsPayloadService()
        service = create_runtime_settings_service(
            state=state,
            auth_service=auth_service,
            settings_payload_service=settings_payload_service,
            apply_runtime_settings=lambda _settings: False,
        )

        self.assertIs(service.read_local_config, read_local_config)
        self.assertIs(service.write_local_config, write_local_config)
        self.assertEqual(service.runtime_config(), {"check_rounds": 2})
        self.assertEqual(service.public_settings(), {"check_rounds": 2})
        self.assertEqual(service.auth_password(), "secret")
        self.assertEqual(service.make_auth_token(), "token")
        self.assertEqual(service.session_seconds(), 60)


class RuntimeCapabilitiesServiceTest(unittest.TestCase):
    def test_payload_uses_dynamic_runtime_values(self):
        deep_check = FakeDeepCheckService()
        fetch = FakeFetchService()
        current = {"max": 30, "limit": 100}
        service = RuntimeCapabilitiesService(
            deep_check_service=deep_check,
            fetch_service=fetch,
            target_profiles=lambda: [{"id": "generic"}],
            max_concurrent=lambda: current["max"],
            max_concurrent_limit=lambda: current["limit"],
            settings_provider=lambda: {"timeout": 15},
        )

        current.update({"max": 60, "limit": 200})
        payload = service.payload()

        self.assertEqual(payload["max_concurrent"], 60)
        self.assertEqual(payload["max_concurrent_limit"], 200)
        self.assertEqual(payload["target_profiles"], [{"id": "generic"}])
        self.assertEqual(payload["proxy_sources"], [{"id": "fake"}])
        self.assertEqual(payload["settings"], {"timeout": 15})

    def test_create_runtime_capabilities_service_uses_live_state(self):
        state = FakeRuntimeState()
        service = create_runtime_capabilities_service(
            state=state,
            deep_check_service=FakeDeepCheckService(),
            fetch_service=FakeFetchService(),
            settings_provider=lambda: {"timeout": 15},
            target_profiles=({"id": "generic"},),
        )

        state.max_concurrent = 60
        state.max_concurrent_limit = 120
        payload = service.payload()

        self.assertEqual(payload["max_concurrent"], 60)
        self.assertEqual(payload["max_concurrent_limit"], 120)
        self.assertEqual(payload["target_profiles"], [{"id": "generic"}])


class ResolveRuntimeSettingsTest(unittest.TestCase):
    def test_resolve_runtime_settings_clamps_values_and_updates_password(self):
        resolved, password_changed = resolve_runtime_settings(
            {
                "max_check_rounds": 20,
                "check_rounds": 99,
                "max_concurrent_limit": 2000,
                "max_concurrent": 5000,
                "timeout": 1,
                "detect_timeout": 999,
                "auth_session_days": 500,
                "log_limit": 5,
                "timezone": "Asia/Shanghai",
                "auth_password": "new-secret",
            },
            current_runtime(),
            normalize_timezone=lambda value: value if value == "Asia/Shanghai" else "UTC",
        )

        self.assertTrue(password_changed)
        self.assertEqual(resolved["max_check_rounds"], 10)
        self.assertEqual(resolved["check_rounds"], 10)
        self.assertEqual(resolved["max_concurrent_limit"], 1000)
        self.assertEqual(resolved["max_concurrent"], 1000)
        self.assertEqual(resolved["timeout"], 3)
        self.assertEqual(resolved["detect_timeout"], 120)
        self.assertEqual(resolved["auth_session_days"], 365)
        self.assertEqual(resolved["auth_session_seconds"], 365 * 86400)
        self.assertEqual(resolved["log_limit"], 20)
        self.assertEqual(resolved["app_timezone"], "Asia/Shanghai")
        self.assertEqual(resolved["auth_password"], "new-secret")
        self.assertEqual(resolved["auth_session_secret"], "new-secret")

    def test_resolve_runtime_settings_keeps_password_when_env_locked(self):
        resolved, password_changed = resolve_runtime_settings(
            {"auth_password": "new-secret"},
            current_runtime(),
            normalize_timezone=lambda value: value,
            password_env=True,
        )

        self.assertFalse(password_changed)
        self.assertEqual(resolved["auth_password"], "old-secret")
        self.assertEqual(resolved["auth_session_secret"], "old-session-secret")

    def test_resolve_runtime_settings_keeps_secret_when_secret_env_locked(self):
        resolved, password_changed = resolve_runtime_settings(
            {"auth_password": "new-secret"},
            current_runtime(),
            normalize_timezone=lambda value: value,
            secret_env=True,
        )

        self.assertTrue(password_changed)
        self.assertEqual(resolved["auth_password"], "new-secret")
        self.assertEqual(resolved["auth_session_secret"], "old-session-secret")


def current_runtime():
    return {
        "timeout": 15,
        "detect_timeout": 20,
        "max_concurrent": 30,
        "max_concurrent_limit": 100,
        "check_rounds": 2,
        "max_check_rounds": 5,
        "log_limit": 100,
        "auth_password": "old-secret",
        "auth_session_days": 7,
        "auth_session_seconds": 7 * 86400,
        "auth_session_secret": "old-session-secret",
        "app_timezone": "UTC",
    }


class FakeSettingsState:
    auth_password = "secret"
    auth_session_seconds = 60


class SimpleAuthService:
    def make_token(self):
        return "token"


class SimpleSettingsPayloadService:
    def runtime_config(self):
        return {"check_rounds": 2}

    def public_settings(self):
        return {"check_rounds": 2}


class FakeDeepCheckService:
    available = True
    xvfb_available = False


class FakeRuntimeState:
    max_concurrent = 30
    max_concurrent_limit = 100


class FakeFetchService:
    available = True

    def sources(self):
        return [{"id": "fake"}]


if __name__ == "__main__":
    unittest.main()
