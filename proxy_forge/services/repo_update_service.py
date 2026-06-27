from proxy_forge.config import REPO_UPDATE_POLICIES
from proxy_forge.services.repo_service import (
    merge_repo_results,
    result_matches_policy,
    result_to_repo_item,
)


class RepoUpdateService:
    def __init__(
        self,
        *,
        repo_update_policies=REPO_UPDATE_POLICIES,
        merge_repo_results_func=merge_repo_results,
    ):
        self.repo_update_policies = tuple(repo_update_policies)
        self.merge_repo_results_func = merge_repo_results_func

    def merge_repo_results(self, *, token, repo, results, checked_inputs, policy):
        return self.merge_repo_results_func(
            token,
            repo,
            results,
            checked_inputs,
            policy,
            self.repo_update_policies,
        )
