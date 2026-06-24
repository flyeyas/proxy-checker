import unittest

from proxy_checker.services.repo_update_service import RepoUpdateService


class RepoUpdateServiceTest(unittest.TestCase):
    def test_merge_repo_results_passes_configured_policies(self):
        calls = []

        def merge_repo_results_func(token, repo, results, checked_inputs, policy, repo_update_policies):
            calls.append({
                "token": token,
                "repo": repo,
                "results": results,
                "checked_inputs": checked_inputs,
                "policy": policy,
                "repo_update_policies": repo_update_policies,
            })
            return {"repo_count": 1}

        service = RepoUpdateService(
            repo_update_policies=("stable_only", "grade_ab_only"),
            merge_repo_results_func=merge_repo_results_func,
        )

        summary = service.merge_repo_results(
            token="demo",
            repo=[{"proxy": "old:1"}],
            results=[{"proxy": "new:1", "grade": "A"}],
            checked_inputs=["new:1"],
            policy="grade_ab_only",
        )

        self.assertEqual(summary, {"repo_count": 1})
        self.assertEqual(calls, [{
            "token": "demo",
            "repo": [{"proxy": "old:1"}],
            "results": [{"proxy": "new:1", "grade": "A"}],
            "checked_inputs": ["new:1"],
            "policy": "grade_ab_only",
            "repo_update_policies": ("stable_only", "grade_ab_only"),
        }])


if __name__ == "__main__":
    unittest.main()
