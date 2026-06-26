"""Runs backend — JSONL append-only storage.

Phase 4 implementation: each run log entry is stored as one JSON line.
Inserts are O(1) file appends; updates rewrite the file (infrequent).
Backward-compatible: auto-migrates legacy runs.json on first access.
"""

import json
import os
import threading
import time

from proxy_checker.storage.files import atomic_write_json, read_json_file


def _compact(entry):
    if not isinstance(entry, dict):
        return None
    log_id = str(entry.get("id") or "").strip()
    if not log_id:
        return None
    out = {
        "id": log_id,
        "type": str(entry.get("type") or "manual"),
        "status": str(entry.get("status") or "running"),
        "started_at": int(entry.get("started_at") or time.time()),
    }
    for key in (
        "finished_at", "duration_seconds", "session_id", "reason", "target_profile",
        "target_name", "rounds", "max_concurrent", "detect_mode", "repo_update_policy",
        "schedule_type", "interval_hours", "daily_time", "timezone", "source_count",
        "repo_input_count", "repo_count", "input_count", "skipped", "total", "done",
        "valid_count", "unstable_count", "invalid_count", "repo_added", "repo_updated",
        "repo_removed", "error",
    ):
        value = entry.get(key)
        if value is not None and value != "":
            out[key] = value
    return out


def _parse_jsonl(path):
    items = []
    if not os.path.isfile(path):
        return items
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            compacted = _compact(item)
            if compacted:
                items.append(compacted)
    return items


def _write_jsonl(path, items):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


class RunsBackend:
    DEFAULT_LIMIT = 100

    def __init__(self, jsonl_path, default_limit=None):
        self._path = jsonl_path
        self._legacy_path = self._resolve_legacy_path()
        self._lock = threading.Lock()
        self._default_limit = default_limit or self.DEFAULT_LIMIT
        self._migrated = False

    def _resolve_legacy_path(self):
        if self._path.endswith(".jsonl"):
            return self._path[:-1]  # runs.jsonl -> runs.json
        return None

    def _maybe_migrate_legacy(self):
        if self._migrated:
            return
        self._migrated = True
        if os.path.isfile(self._path):
            return
        if not self._legacy_path or not os.path.isfile(self._legacy_path):
            return
        data = read_json_file(self._legacy_path, [])
        if not isinstance(data, list):
            return
        items = [_compact(item) for item in data]
        items = [item for item in items if item]
        if items:
            items.sort(key=lambda item: int(item.get("started_at") or 0), reverse=True)
            _write_jsonl(self._path, items)

    def set_default_limit(self, limit):
        try:
            parsed = int(limit)
        except (TypeError, ValueError):
            return self._default_limit
        self._default_limit = max(20, min(1000, parsed))
        return self._default_limit

    def path(self):
        return self._path

    def _read_all(self):
        self._maybe_migrate_legacy()
        return _parse_jsonl(self._path)

    def _write_all(self, items):
        cleaned = [_compact(item) for item in items]
        cleaned = [item for item in cleaned if item]
        cleaned.sort(key=lambda item: int(item.get("started_at") or 0), reverse=True)
        capped = cleaned[: self._default_limit]
        _write_jsonl(self._path, capped)
        return capped

    def list(self, limit=None):
        with self._lock:
            items = self._read_all()
        items.sort(key=lambda item: int(item.get("started_at") or 0), reverse=True)
        if limit is None:
            return items[: self._default_limit]
        return items[: int(limit)]

    def insert(self, entry):
        entry = dict(entry or {})
        now = int(time.time())
        entry.setdefault("id", f"log_{now}_{threading.get_ident()}")
        entry.setdefault("started_at", now)
        entry.setdefault("status", "running")
        compacted = _compact(entry)
        if not compacted:
            return entry.get("id", "")
        with self._lock:
            self._maybe_migrate_legacy()
            directory = os.path.dirname(self._path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(compacted, ensure_ascii=False, separators=(",", ":")) + "\n")
        return compacted["id"]

    def update(self, run_id, fields):
        now = int(time.time())
        with self._lock:
            items = self._read_all()
            found = False
            for item in items:
                if item.get("id") != run_id:
                    continue
                item.update(fields or {})
                item.setdefault("finished_at", now)
                item["duration_seconds"] = max(
                    0,
                    int(item.get("finished_at") or now) - int(item.get("started_at") or now),
                )
                found = True
                break
            if not found:
                entry = dict(fields or {})
                entry["id"] = run_id
                entry.setdefault("started_at", now)
                entry.setdefault("finished_at", now)
                entry["duration_seconds"] = 0
                items.insert(0, entry)
            return self._write_all(items)

    def clear(self):
        with self._lock:
            _write_jsonl(self._path, [])

    def replace_all(self, entries):
        with self._lock:
            return self._write_all(entries)
