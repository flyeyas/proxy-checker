import unittest

from proxy_forge.services.runtime_options_service import RuntimeOptionsService, create_runtime_options_service


class RuntimeOptionsServiceTest(unittest.TestCase):
    def setUp(self):
        self.current = {
            "timezone": "UTC",
            "rounds": 2,
            "max_rounds": 5,
            "max_concurrent": 30,
            "max_concurrent_limit": 100,
            "policies": ("stable_only", "grade_ab_only"),
        }
        self.service = RuntimeOptionsService(
            app_timezone=lambda: self.current["timezone"],
            check_rounds=lambda: self.current["rounds"],
            max_check_rounds=lambda: self.current["max_rounds"],
            max_concurrent=lambda: self.current["max_concurrent"],
            max_concurrent_limit=lambda: self.current["max_concurrent_limit"],
            repo_update_policies=lambda: self.current["policies"],
            target_profiles=lambda: [{"id": "generic", "name": "Generic"}, {"id": "chat", "name": "Chat"}],
            timezone_ids=lambda: {"UTC", "Asia/Shanghai"},
        )

    def test_check_options_use_current_runtime_values(self):
        self.current.update({"rounds": 3, "max_rounds": 4, "max_concurrent": 20, "max_concurrent_limit": 50})

        self.assertEqual(self.service.normalize_rounds(9), 4)
        self.assertEqual(self.service.normalize_max_concurrent(99), 50)
        self.assertEqual(self.service.normalize_target_profile("chat"), "chat")
        self.assertEqual(self.service.normalize_target_profile("missing"), "generic")
        self.assertEqual(self.service.get_target_profile_name("chat"), "Chat")

    def test_auto_config_uses_current_defaults_and_policy_fallback(self):
        self.current.update({"rounds": 4, "max_concurrent": 40, "timezone": "Asia/Shanghai"})

        config = self.service.normalize_auto_config({
            "enabled": True,
            "repo_update_policy": "missing",
            "timezone": "bad",
            "target_profile": "chat",
        })

        self.assertEqual(config["rounds"], 4)
        self.assertEqual(config["max_concurrent"], 40)
        self.assertEqual(config["repo_update_policy"], "stable_only")
        self.assertEqual(config["timezone"], "UTC")
        self.assertEqual(config["target_profile"], "chat")
        self.assertEqual(self.service.default_auto_config()["timezone"], "Asia/Shanghai")

    def test_time_helpers(self):
        self.assertEqual(self.service.normalize_timezone("bad"), "UTC")
        self.assertEqual(str(self.service.get_timezone("UTC")), "UTC")
        payload = self.service.server_time_payload("UTC")
        self.assertEqual(payload["timezone"], "UTC")

    def test_create_runtime_options_service_uses_live_state(self):
        state = FakeRuntimeState()
        service = create_runtime_options_service(state)

        state.check_rounds = 4
        state.max_concurrent = 50

        self.assertEqual(service.default_auto_config()["rounds"], 4)
        self.assertEqual(service.default_auto_config()["max_concurrent"], 50)


class FakeRuntimeState:
    app_timezone = "UTC"
    check_rounds = 2
    max_check_rounds = 5
    max_concurrent = 30
    max_concurrent_limit = 100


if __name__ == "__main__":
    unittest.main()
