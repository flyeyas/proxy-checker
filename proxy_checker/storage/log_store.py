"""Legacy run-log storage API.

Phase 2 thin wrapper: all functions delegate to ``TenantStorage(token).runs``.

The historical module-level ``_log_limit`` (set via ``set_log_limit``) is
preserved as a process-wide default and applied to every freshly-created
``RunsBackend`` instance, matching the legacy semantics where one global
limit controlled all tokens.
"""

from proxy_checker.config import LOG_LIMIT
from proxy_checker.storage.runs_backend import _compact as compact_log
from proxy_checker.storage.tenant import TenantStorage

__all__ = [
    "compact_log",
    "log_json_path",
    "set_log_limit",
    "read_logs",
    "write_logs",
    "start_log",
    "finish_log",
    "clear_logs",
]


_log_limit = LOG_LIMIT


def _runs(token):
    storage = TenantStorage(token)
    storage.runs.set_default_limit(_log_limit)
    return storage.runs


def set_log_limit(limit):
    global _log_limit
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return _log_limit
    _log_limit = max(20, min(1000, parsed))
    return _log_limit


def log_json_path(token):
    return TenantStorage(token).runs.path()


def read_logs(token):
    return _runs(token).list()


def write_logs(token, logs):
    return _runs(token).replace_all(logs)


def start_log(token, entry):
    return _runs(token).insert(entry)


def finish_log(token, log_id, updates):
    return _runs(token).update(log_id, updates)


def clear_logs(token):
    _runs(token).clear()
