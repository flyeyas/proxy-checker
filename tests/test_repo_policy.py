import unittest
from unittest.mock import patch

from proxy_checker.services.repo_service import (
    filter_repo_by_grades,
    merge_repo_results,
    repo_item_matches_grades,
    result_matches_policy,
)


class RepoPolicyTest(unittest.TestCase):
    def test_result_matches_policy(self):
        self.assertTrue(result_matches_policy({"grade": "A"}, "grade_a_only"))
        self.assertFalse(result_matches_policy({"grade": "B"}, "grade_a_only"))
        self.assertTrue(result_matches_policy({"grade": "B"}, "grade_b_only"))
        self.assertTrue(result_matches_policy({"grade": "A"}, "grade_ab_only"))
        self.assertTrue(result_matches_policy({"grade": "B"}, "grade_ab_only"))
        self.assertFalse(result_matches_policy({"grade": "C"}, "grade_ab_only"))
        self.assertTrue(result_matches_policy({"grade": "D", "unstable": True}, "include_unstable"))
        self.assertTrue(result_matches_policy({"grade": "F"}, "archive_all"))
        self.assertTrue(result_matches_policy({"grade": "C"}, "stable_only"))
        self.assertFalse(result_matches_policy({"grade": "F", "valid": False}, "stable_only"))

    def test_filter_repo_by_grades(self):
        repo = [
            {"proxy": "a:1", "grade": "a"},
            {"proxy": "b:1", "grade": "B"},
            {"proxy": "c:1", "grade": "C"},
            {"proxy": "", "grade": "A"},
        ]

        filtered = filter_repo_by_grades(repo, {"A", "B"})

        self.assertTrue(repo_item_matches_grades({"grade": "a"}, {"A"}))
        self.assertEqual([item["proxy"] for item in filtered], ["a:1", "b:1"])

    def test_merge_repo_results_applies_grade_ab_policy(self):
        repo = [
            {"proxy": "old:1", "grade": "A", "added": 10},
            {"proxy": "bad:1", "grade": "A", "added": 20},
        ]
        results = [
            {"original": "old:1", "proxy": "old:1", "grade": "B", "valid": True},
            {"original": "bad:1", "proxy": "bad:1", "grade": "F", "valid": False},
            {"original": "new:1", "proxy": "new:1", "grade": "A", "valid": True},
        ]

        with patch("proxy_checker.services.repo_service.write_repo_data", side_effect=lambda _token, data: data):
            summary = merge_repo_results(
                "token",
                repo,
                results,
                ["old:1", "bad:1", "new:1"],
                "grade_ab_only",
                ("stable_only", "grade_ab_only"),
            )

        self.assertEqual(summary["repo_count"], 2)
        self.assertEqual(summary["repo_added"], 1)
        self.assertEqual(summary["repo_updated"], 1)
        self.assertEqual(summary["repo_removed"], 1)


if __name__ == "__main__":
    unittest.main()
