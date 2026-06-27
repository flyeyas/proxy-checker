"""Repository backend.

Owns the pure normalization helpers (`compact_repo_item`, `compact_repo`,
`merge_repo_data`) and the JSON+TXT persistence for a single token. The
legacy `repo_store` module re-exports these helpers so callers using the
old API continue to work unchanged.
"""

import os
import time

from proxy_forge.storage.files import atomic_write_json, atomic_write_text, read_json_file
from proxy_forge.utils import proxy_key


def compact_repo_item(item):
    if not isinstance(item, dict):
        item = {"proxy": str(item or "")}
    proxy = str(item.get("proxy", "")).strip()
    if not proxy:
        return None
    now = int(time.time() * 1000)
    compact = {"proxy": proxy, "grade": str(item.get("grade") or "?")}
    for key in ("latency", "ip", "country", "ip_type", "recommended_use", "target_profile", "target_name"):
        value = item.get(key)
        if value is not None and value != "":
            compact[key] = value
    for key in ("service_reachable", "api_reachable", "cf_bypass"):
        if item.get(key) is True:
            compact[key] = True
    compact["added"] = item.get("added") or now
    compact["updated"] = item.get("updated") or compact["added"]
    return compact


def compact_repo(repo):
    out = []
    seen = set()
    for item in repo or []:
        compact = compact_repo_item(item)
        if not compact:
            continue
        key = proxy_key(compact["proxy"])
        if key in seen:
            continue
        seen.add(key)
        out.append(compact)
    return out


def merge_repo_data(existing, incoming):
    merged = compact_repo(existing)
    index_by_key = {proxy_key(item["proxy"]): i for i, item in enumerate(merged)}
    for item in compact_repo(incoming):
        key = proxy_key(item["proxy"])
        if not key:
            continue
        index = index_by_key.get(key)
        if index is None:
            index_by_key[key] = len(merged)
            merged.append(item)
        else:
            previous = merged[index]
            item["added"] = previous.get("added") or item.get("added")
            merged[index] = {**previous, **item}
    return compact_repo(merged)


class RepoBackend:
    def __init__(self, json_path, txt_path):
        self._json_path = json_path
        self._txt_path = txt_path

    def json_path(self):
        return self._json_path

    def txt_path(self):
        return self._txt_path

    def read(self):
        if os.path.isfile(self._json_path):
            data = read_json_file(self._json_path, [])
            if isinstance(data, list):
                return compact_repo(data)
        if not os.path.isfile(self._txt_path):
            return []
        with open(self._txt_path, "r", encoding="utf-8") as f:
            return compact_repo({"proxy": line.strip()} for line in f if line.strip())

    def write(self, repo):
        repo = compact_repo(repo)
        atomic_write_json(self._json_path, repo)
        atomic_write_text(self._txt_path, "\n".join(item["proxy"] for item in repo))
        return repo

    def merge(self, incoming):
        return merge_repo_data(self.read(), incoming)

    def save_payload(self, incoming, mode="merge", base_count=None):
        mode = mode if mode in ("merge", "replace") else "merge"
        incoming_repo = compact_repo(incoming)
        existing_repo = self.read()
        current_count = len(existing_repo)
        try:
            expected_count = int(base_count)
        except (TypeError, ValueError):
            expected_count = None

        if mode == "replace":
            if expected_count is None and current_count > len(incoming_repo):
                return None, {
                    "ok": False,
                    "stale_repo": True,
                    "current_count": current_count,
                    "submitted_count": len(incoming_repo),
                    "error": "云端仓库已有更多代理，请先刷新云端仓库后再删除或覆盖",
                }
            if expected_count is not None and expected_count != current_count:
                return None, {
                    "ok": False,
                    "stale_repo": True,
                    "current_count": current_count,
                    "submitted_count": len(incoming_repo),
                    "base_count": expected_count,
                    "error": "云端仓库已被更新，请先刷新云端仓库后再删除或覆盖",
                }
            saved = self.write(incoming_repo)
        else:
            saved = self.write(merge_repo_data(existing_repo, incoming_repo))

        return saved, {
            "ok": True,
            "mode": mode,
            "count": len(saved),
            "current_count": current_count,
            "submitted_count": len(incoming_repo),
        }

    def index_by_key(self, repo=None):
        repo = self.read() if repo is None else compact_repo(repo)
        return {proxy_key(item["proxy"]): item for item in repo}
