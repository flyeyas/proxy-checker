import os
import threading
import time

from proxy_checker.config import LOG_DIR, LOG_LIMIT
from proxy_checker.storage.files import atomic_write_json, read_json_file
from proxy_checker.utils import sanitize_token

_log_limit = LOG_LIMIT


def set_log_limit(limit):
    global _log_limit
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return _log_limit
    _log_limit = max(20, min(1000, parsed))
    return _log_limit


def log_json_path(token):
    return os.path.join(LOG_DIR, f"{sanitize_token(token)}.json")


def compact_log(entry):
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


def read_logs(token):
    data = read_json_file(log_json_path(token), [])
    if not isinstance(data, list):
        return []
    logs = [compact_log(item) for item in data]
    return [item for item in logs if item]


def write_logs(token, logs):
    cleaned = [compact_log(item) for item in logs]
    cleaned = [item for item in cleaned if item]
    cleaned.sort(key=lambda item: int(item.get("started_at") or 0), reverse=True)
    atomic_write_json(log_json_path(token), cleaned[:_log_limit])
    return cleaned[:_log_limit]


def start_log(token, entry):
    token = sanitize_token(token)
    now = int(time.time())
    entry = dict(entry or {})
    entry.setdefault("id", f"log_{now}_{threading.get_ident()}")
    entry.setdefault("started_at", now)
    entry.setdefault("status", "running")
    logs = read_logs(token)
    logs.insert(0, entry)
    write_logs(token, logs)
    return entry["id"]


def finish_log(token, log_id, updates):
    token = sanitize_token(token)
    logs = read_logs(token)
    now = int(time.time())
    found = False
    for item in logs:
        if item.get("id") != log_id:
            continue
        item.update(updates or {})
        item.setdefault("finished_at", now)
        item["duration_seconds"] = max(0, int(item.get("finished_at") or now) - int(item.get("started_at") or now))
        found = True
        break
    if not found:
        entry = dict(updates or {})
        entry["id"] = log_id
        entry.setdefault("started_at", now)
        entry.setdefault("finished_at", now)
        entry["duration_seconds"] = 0
        logs.insert(0, entry)
    return write_logs(token, logs)


def clear_logs(token):
    atomic_write_json(log_json_path(token), [])
