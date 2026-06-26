"""Legacy repo storage API.

Phase 2 thin wrapper: all functions delegate to ``TenantStorage(token).repo``.
Pure normalization helpers live in ``repo_backend`` and are re-exported here
so existing imports keep working.
"""

from proxy_checker.storage.repo_backend import compact_repo, compact_repo_item, merge_repo_data
from proxy_checker.storage.tenant import TenantStorage

__all__ = [
    "compact_repo",
    "compact_repo_item",
    "merge_repo_data",
    "repo_json_path",
    "repo_txt_path",
    "read_repo_data",
    "write_repo_data",
    "save_repo_payload",
]


def repo_json_path(token):
    return TenantStorage(token).repo.json_path()


def repo_txt_path(token):
    return TenantStorage(token).repo.txt_path()


def read_repo_data(token):
    return TenantStorage(token).repo.read()


def write_repo_data(token, repo):
    return TenantStorage(token).repo.write(repo)


def save_repo_payload(token, incoming, mode="merge", base_count=None):
    return TenantStorage(token).repo.save_payload(incoming, mode=mode, base_count=base_count)
