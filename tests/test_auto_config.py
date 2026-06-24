import unittest
from datetime import timezone

from proxy_checker.services.auto_config_service import (
    compute_next_run,
    default_auto_config,
    default_auto_state,
    normalize_auto_config,
    normalize_daily_time,
    normalize_interval_hours,
)


class AutoConfigTest(unittest.TestCase):
    def test_defaults_and_bounds(self):
        config = default_auto_config("UTC", 2, 30)
        self.assertEqual(config["timezone"], "UTC")
        self.assertEqual(config["rounds"], 2)
        self.assertEqual(config["max_concurrent"], 30)
        self.assertEqual(default_auto_state({"enabled": True})["status"], "idle")
        self.assertEqual(normalize_interval_hours("bad"), 6)
        self.assertEqual(normalize_interval_hours(999), 720)
        self.assertEqual(normalize_daily_time("25:90"), "23:59")
        self.assertEqual(normalize_daily_time("7"), "07:00")

    def test_normalize_auto_config_falls_back(self):
        config = normalize_auto_config(
            {
                "enabled": True,
                "schedule_type": "bad",
                "interval_hours": 0,
                "daily_time": "7",
                "timezone": "bad",
                "target_profile": "missing",
                "detect_mode": "bad",
                "repo_update_policy": "bad",
            },
            app_timezone="UTC",
            check_rounds=2,
            max_concurrent=30,
            repo_update_policies=("stable_only", "grade_ab_only"),
            normalize_target_profile=lambda value: value if value == "generic" else "generic",
            normalize_max_concurrent=lambda value: min(200, max(1, int(value))),
            normalize_timezone=lambda value: value if value == "UTC" else "UTC",
        )

        self.assertTrue(config["enabled"])
        self.assertEqual(config["schedule_type"], "interval")
        self.assertEqual(config["interval_hours"], 0.01)
        self.assertEqual(config["daily_time"], "07:00")
        self.assertEqual(config["timezone"], "UTC")
        self.assertEqual(config["target_profile"], "generic")
        self.assertEqual(config["detect_mode"], "skip")
        self.assertEqual(config["repo_update_policy"], "stable_only")

    def test_compute_next_run_interval(self):
        def normalize_config(config):
            return {
                "enabled": True,
                "schedule_type": "interval",
                "interval_hours": config.get("interval_hours", 1),
            }

        next_run = compute_next_run(
            {"interval_hours": 1},
            normalize_auto_config=normalize_config,
            get_timezone=lambda _timezone_id: timezone.utc,
            now=100,
        )
        self.assertEqual(next_run, 3700)


if __name__ == "__main__":
    unittest.main()
