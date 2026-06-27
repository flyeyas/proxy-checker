"""Tenant storage entry point.

A `TenantStorage` exposes the four resource backends (`repo`, `checked`,
`auto`, `runs`) for a single token. Path resolution is delegated to a
`StorageLayout` strategy. The supported layout is `TenantDirLayout`, one
directory per token: `data/<token>/{repo.json, repo.txt, checked.txt,
auto.json, runs.jsonl}`.
"""

import os

from proxy_forge.config import DATA_DIR
from proxy_forge.storage.auto_backend import AutoBackend
from proxy_forge.storage.checked_backend import CheckedBackend
from proxy_forge.storage.paths import list_tenant_dirs, tenant_dir_path
from proxy_forge.storage.repo_backend import RepoBackend
from proxy_forge.storage.runs_backend import RunsBackend
from proxy_forge.utils import sanitize_token


REPO_JSON_NAME = "repo.json"
REPO_TXT_NAME = "repo.txt"
CHECKED_TXT_NAME = "checked.txt"
AUTO_JSON_NAME = "auto.json"
RUNS_JSONL_NAME = "runs.jsonl"


class TenantDirLayout:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or DATA_DIR

    def tenant_dir(self, token):
        return tenant_dir_path(self.data_dir, token)

    def repo_paths(self, token):
        base = self.tenant_dir(token)
        return os.path.join(base, REPO_JSON_NAME), os.path.join(base, REPO_TXT_NAME)

    def checked_path(self, token):
        return os.path.join(self.tenant_dir(token), CHECKED_TXT_NAME)

    def auto_path(self, token):
        return os.path.join(self.tenant_dir(token), AUTO_JSON_NAME)

    def runs_path(self, token):
        return os.path.join(self.tenant_dir(token), RUNS_JSONL_NAME)

    def list_tokens(self):
        return list_tenant_dirs(self.data_dir, AUTO_JSON_NAME)


def default_layout():
    return TenantDirLayout()


class TenantStorage:
    def __init__(self, token, layout=None):
        self.token = sanitize_token(token)
        self.layout = layout or default_layout()
        repo_json, repo_txt = self.layout.repo_paths(self.token)
        self.repo = RepoBackend(repo_json, repo_txt)
        self.checked = CheckedBackend(self.layout.checked_path(self.token))
        self.auto = AutoBackend(self.layout.auto_path(self.token))
        self.runs = RunsBackend(self.layout.runs_path(self.token))

    def close(self):
        self.checked.close()


def create_tenant_storage_factory(layout=None):
    layout = layout or default_layout()

    def factory(token):
        return TenantStorage(token, layout=layout)

    return factory


def list_tenant_tokens(layout=None):
    layout = layout or default_layout()
    return layout.list_tokens()
