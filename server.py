import json
import time
import os
import sys
import base64
import threading
import asyncio
import logging
import hashlib
import hmac
import select
import socket
import ssl
from urllib.parse import unquote, urlsplit
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import HTTPServer
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from proxy_check import CheckConfig, DEFAULT_TARGET_CHAT, ProxyCheckEngine, TARGET_PROFILE_OPTIONS
from proxy_checker.config import (
    APP_TIMEZONE,
    AUTH_COOKIE_NAME,
    AUTH_PASSWORD,
    AUTH_SESSION_DAYS,
    AUTH_SESSION_SECRET,
    AUTH_SESSION_SECONDS,
    AUTO_DIR,
    BASE_DIR,
    CHECK_ROUNDS,
    CONFIG_LOCAL_PATH,
    DETECT_TIMEOUT,
    LOG_FILE_PATH,
    LOG_LIMIT,
    MAX_CHECK_ROUNDS,
    MAX_CONCURRENT,
    MAX_CONCURRENT_LIMIT,
    PORT,
    PROXY_GATEWAY_BIND,
    PROXY_GATEWAY_ENABLED,
    PROXY_GATEWAY_GRADES,
    PROXY_GATEWAY_PORT,
    PROXY_GATEWAY_TIMEOUT,
    PROXY_GATEWAY_TOKEN,
    REPO_DIR,
    REPO_UPDATE_POLICIES,
    TIMEOUT,
    TIMEZONE_IDS,
    TIMEZONE_OPTIONS,
)
from proxy_checker.storage.files import (
    atomic_write_json,
    atomic_write_text,
    read_json_file as read_json_file_base,
)
from proxy_checker.storage.checked_store import (
    append_checked_list,
    checked_txt_path,
    read_checked_list,
    write_checked_list,
)
from proxy_checker.storage.repo_store import (
    compact_repo,
    compact_repo_item,
    read_repo_data,
    save_repo_payload,
    write_repo_data,
)
from proxy_checker.storage.log_store import (
    clear_logs,
    finish_log,
    read_logs,
    set_log_limit,
    start_log,
)
from proxy_checker.utils import normalize_proxy_list, proxy_key, sanitize_token

# ============================================================
# My Repository — save/retrieve repo proxies as txt
# ============================================================

# === Fetch free proxies from external sources ===
try:
    from fetch_proxies import fetch_proxies, PROXY_SOURCES
    FETCH_PROXIES_AVAILABLE = True
except ImportError:
    FETCH_PROXIES_AVAILABLE = False

# === Try to import nodriver for deep check ===
NODRIVER_AVAILABLE = False
try:
    import nodriver
    NODRIVER_AVAILABLE = True
except ImportError:
    pass

# === Try to install Xvfb for headless Chrome ===
XVFB_AVAILABLE = False
try:
    import subprocess
    _xvfb_check = subprocess.run(["which", "Xvfb"], capture_output=True, timeout=3)
    XVFB_AVAILABLE = _xvfb_check.returncode == 0
except Exception:
    pass

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
    ]
)
log = logging.getLogger('vpntest')

TARGET_CHAT = DEFAULT_TARGET_CHAT
check_engine = ProxyCheckEngine(
    CheckConfig(
        timeout=TIMEOUT,
        detect_timeout=DETECT_TIMEOUT,
        check_rounds=CHECK_ROUNDS,
    )
)

sessions = {}
sessions_lock = threading.Lock()
auto_runtime = {}
auto_stopped_results = {}
auto_lock = threading.Lock()
proxy_gateway_lock = threading.Lock()
proxy_gateway_index = 0
TARGET_PROFILE_IDS = {str(item["id"]) for item in TARGET_PROFILE_OPTIONS}


def normalize_target_profile(value):
    profile_id = str(value or "generic")
    return profile_id if profile_id in TARGET_PROFILE_IDS else "generic"


def get_target_profile_name(value):
    profile_id = normalize_target_profile(value)
    for item in TARGET_PROFILE_OPTIONS:
        if item["id"] == profile_id:
            return item["name"]
    return profile_id


def normalize_max_concurrent(value):
    try:
        concurrent = int(value)
    except (TypeError, ValueError):
        concurrent = MAX_CONCURRENT
    return max(1, min(MAX_CONCURRENT_LIMIT, concurrent))


def normalize_rounds(value):
    try:
        rounds = int(value)
    except (TypeError, ValueError):
        rounds = CHECK_ROUNDS
    return max(1, min(MAX_CHECK_ROUNDS, rounds))


def normalize_interval_hours(value):
    try:
        interval_hours = float(value)
    except (TypeError, ValueError):
        interval_hours = 6
    return max(0.01, min(720, interval_hours))


def normalize_timeout(value, default):
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = default
    return max(3, min(120, timeout))


def normalize_timezone(value):
    timezone_id = str(value or APP_TIMEZONE or "UTC").strip()
    return timezone_id if timezone_id in TIMEZONE_IDS else "UTC"


def get_timezone(timezone_id):
    timezone_id = normalize_timezone(timezone_id)
    if ZoneInfo is not None:
        try:
            return ZoneInfo(timezone_id)
        except Exception:
            pass
    if timezone_id == "Asia/Shanghai":
        return timezone(timedelta(hours=8))
    if timezone_id == "Asia/Tokyo":
        return timezone(timedelta(hours=9))
    if timezone_id == "Asia/Bangkok":
        return timezone(timedelta(hours=7))
    if timezone_id == "Asia/Dubai":
        return timezone(timedelta(hours=4))
    if timezone_id == "Europe/Berlin":
        return timezone(timedelta(hours=1))
    if timezone_id == "Europe/London":
        return timezone.utc
    if timezone_id == "America/New_York":
        return timezone(timedelta(hours=-5))
    if timezone_id == "America/Chicago":
        return timezone(timedelta(hours=-6))
    if timezone_id == "America/Denver":
        return timezone(timedelta(hours=-7))
    if timezone_id == "America/Los_Angeles":
        return timezone(timedelta(hours=-8))
    if timezone_id == "Australia/Sydney":
        return timezone(timedelta(hours=10))
    return timezone.utc


def format_timestamp(timestamp, timezone_id=None):
    if not timestamp:
        return None
    tz_id = normalize_timezone(timezone_id or APP_TIMEZONE)
    dt = datetime.fromtimestamp(float(timestamp), get_timezone(tz_id))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def read_json_file(path, fallback):
    return read_json_file_base(path, fallback, log)


def auto_json_path(token):
    return os.path.join(AUTO_DIR, f"{sanitize_token(token)}.json")


def proxy_gateway_grade_set():
    grades = {
        str(item).strip().upper()
        for item in PROXY_GATEWAY_GRADES.replace(";", ",").split(",")
        if str(item).strip()
    }
    return grades or {"A", "B"}


def proxy_gateway_repo_tokens():
    if PROXY_GATEWAY_TOKEN:
        return [sanitize_token(PROXY_GATEWAY_TOKEN)]
    tokens = set()
    for name in os.listdir(REPO_DIR):
        base, ext = os.path.splitext(name)
        if ext in (".json", ".txt") and base:
            tokens.add(sanitize_token(base))
    return sorted(tokens)


def normalize_upstream_proxy(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw if "://" in raw else f"http://{raw}"
    parsed = urlsplit(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return None
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80)
    if not host or not port:
        return None
    auth = ""
    if parsed.username:
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        auth = f"Proxy-Authorization: Basic {token}\r\n"
    return {
        "raw": raw,
        "scheme": scheme,
        "host": host,
        "port": port,
        "auth": auth,
    }


def proxy_gateway_candidates():
    allowed_grades = proxy_gateway_grade_set()
    candidates = []
    seen = set()
    for token in proxy_gateway_repo_tokens():
        for item in read_repo_data(token):
            grade = str(item.get("grade") or "").upper()
            if grade not in allowed_grades:
                continue
            upstream = normalize_upstream_proxy(item.get("proxy"))
            if not upstream:
                continue
            key = f"{upstream['scheme']}://{upstream['host']}:{upstream['port']}"
            if key in seen:
                continue
            seen.add(key)
            candidates.append(upstream)
    return candidates


def ordered_proxy_gateway_candidates():
    global proxy_gateway_index
    candidates = proxy_gateway_candidates()
    if not candidates:
        return []
    with proxy_gateway_lock:
        start = proxy_gateway_index % len(candidates)
        proxy_gateway_index = (proxy_gateway_index + 1) % len(candidates)
    return candidates[start:] + candidates[:start]


def logs_payload(token):
    timezone_id = APP_TIMEZONE
    logs = read_logs(token)
    for item in logs:
        timezone_id = normalize_timezone(item.get("timezone", APP_TIMEZONE))
        item["started_text"] = format_timestamp(item.get("started_at"), timezone_id)
        item["finished_text"] = format_timestamp(item.get("finished_at"), timezone_id)
    return {
        "logs": logs,
        "count": len(logs),
        "server_time": server_time_payload(timezone_id),
    }


def default_auto_config():
    return {
        "enabled": False,
        "schedule_type": "interval",
        "interval_hours": 6,
        "daily_time": "03:00",
        "timezone": APP_TIMEZONE,
        "target_profile": "generic",
        "rounds": CHECK_ROUNDS,
        "max_concurrent": MAX_CONCURRENT,
        "detect_mode": "skip",
        "repo_update_policy": "stable_only",
    }


def default_auto_state(config=None):
    config = config or default_auto_config()
    return {
        "running": False,
        "status": "disabled" if not config.get("enabled") else "idle",
        "session_id": None,
        "stage": "idle",
        "started_at": None,
        "finished_at": None,
        "last_run_at": None,
        "next_run_at": None,
        "last_summary": None,
        "history": [],
    }


def normalize_daily_time(value):
    raw = str(value or "03:00").strip()
    parts = raw.split(":", 1)
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        hour, minute = 3, 0
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{hour:02d}:{minute:02d}"


def normalize_auto_config(config):
    config = config if isinstance(config, dict) else {}
    defaults = default_auto_config()
    merged = {**defaults, **config}
    schedule_type = str(merged.get("schedule_type") or "interval")
    if schedule_type not in ("interval", "daily"):
        schedule_type = "interval"
    interval_hours = normalize_interval_hours(merged.get("interval_hours", defaults["interval_hours"]))
    detect_mode = str(merged.get("detect_mode") or "skip")
    if detect_mode not in ("skip", "force"):
        detect_mode = "skip"
    repo_update_policy = str(merged.get("repo_update_policy") or "stable_only")
    if repo_update_policy not in REPO_UPDATE_POLICIES:
        repo_update_policy = "stable_only"
    return {
        "enabled": bool(merged.get("enabled")),
        "schedule_type": schedule_type,
        "interval_hours": interval_hours,
        "daily_time": normalize_daily_time(merged.get("daily_time")),
        "timezone": normalize_timezone(merged.get("timezone", APP_TIMEZONE)),
        "target_profile": normalize_target_profile(merged.get("target_profile")),
        "rounds": CHECK_ROUNDS,
        "max_concurrent": normalize_max_concurrent(MAX_CONCURRENT),
        "detect_mode": detect_mode,
        "repo_update_policy": repo_update_policy,
    }


def compute_next_run(config, now=None):
    config = normalize_auto_config(config)
    if not config.get("enabled"):
        return None
    now = time.time() if now is None else float(now)
    if config["schedule_type"] == "daily":
        hour, minute = [int(part) for part in config["daily_time"].split(":", 1)]
        tz = get_timezone(config.get("timezone"))
        current = datetime.fromtimestamp(now, tz)
        target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target.timestamp() <= now:
            target = target + timedelta(days=1)
        return int(target.timestamp())
    return int(now + config["interval_hours"] * 3600)


def server_time_payload(timezone_id=None):
    now = time.time()
    tz_id = normalize_timezone(timezone_id or APP_TIMEZONE)
    return {
        "timestamp": int(now),
        "text": format_timestamp(now, tz_id),
        "timezone": tz_id,
        "server_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "server_timezone": time.strftime("%Z", time.localtime(now)),
    }


def is_auth_enabled():
    return bool(AUTH_PASSWORD)


def make_auth_token():
    issued_at = str(int(time.time()))
    signature = hmac.new(
        AUTH_SESSION_SECRET.encode("utf-8"),
        issued_at.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{issued_at}:{signature}"


def verify_auth_token(token):
    if not is_auth_enabled():
        return True
    try:
        issued_at, signature = str(token or "").split(":", 1)
        issued_at_int = int(issued_at)
    except (TypeError, ValueError):
        return False
    if time.time() - issued_at_int > AUTH_SESSION_SECONDS:
        return False
    expected = hmac.new(
        AUTH_SESSION_SECRET.encode("utf-8"),
        issued_at.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def get_bearer_token(headers):
    auth_header = headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return headers.get("X-Proxy-Auth", "").strip()


def get_cookie_token(cookie_header):
    parsed = cookies.SimpleCookie()
    try:
        parsed.load(cookie_header or "")
    except cookies.CookieError:
        return ""
    morsel = parsed.get(AUTH_COOKIE_NAME)
    return morsel.value if morsel else ""


def is_request_authenticated(headers):
    return verify_auth_token(get_bearer_token(headers) or get_cookie_token(headers.get("Cookie", "")))


def make_auth_cookie(token, max_age=AUTH_SESSION_SECONDS):
    return f"{AUTH_COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax"


def read_local_config():
    if not os.path.isfile(CONFIG_LOCAL_PATH):
        return {}
    data = read_json_file(CONFIG_LOCAL_PATH, {})
    return data if isinstance(data, dict) else {}


def write_local_config(data):
    cleaned = data if isinstance(data, dict) else {}
    atomic_write_json(CONFIG_LOCAL_PATH, cleaned)
    return cleaned


def public_settings_payload():
    return {
        "check_rounds": CHECK_ROUNDS,
        "max_check_rounds": MAX_CHECK_ROUNDS,
        "max_concurrent": MAX_CONCURRENT,
        "max_concurrent_limit": MAX_CONCURRENT_LIMIT,
        "timeout": TIMEOUT,
        "detect_timeout": DETECT_TIMEOUT,
        "auth_session_days": AUTH_SESSION_DAYS,
        "log_limit": LOG_LIMIT,
        "timezone": APP_TIMEZONE,
        "port": PORT,
        "proxy_gateway": {
            "enabled": PROXY_GATEWAY_ENABLED,
            "bind": PROXY_GATEWAY_BIND,
            "port": PROXY_GATEWAY_PORT,
            "grades": sorted(proxy_gateway_grade_set()),
            "token": PROXY_GATEWAY_TOKEN or None,
        },
        "timezone_options": list(TIMEZONE_OPTIONS),
        "password_configurable": "AUTH_PASSWORD" not in os.environ,
    }


def apply_runtime_settings(settings):
    global TIMEOUT, DETECT_TIMEOUT, MAX_CONCURRENT, MAX_CONCURRENT_LIMIT
    global CHECK_ROUNDS, MAX_CHECK_ROUNDS, LOG_LIMIT, AUTH_PASSWORD
    global AUTH_SESSION_DAYS, AUTH_SESSION_SECONDS, AUTH_SESSION_SECRET
    global APP_TIMEZONE, check_engine

    if not isinstance(settings, dict):
        settings = {}
    MAX_CHECK_ROUNDS = max(1, min(10, get_int_from(settings, "max_check_rounds", MAX_CHECK_ROUNDS)))
    CHECK_ROUNDS = max(1, min(MAX_CHECK_ROUNDS, get_int_from(settings, "check_rounds", CHECK_ROUNDS)))
    MAX_CONCURRENT_LIMIT = max(1, min(1000, get_int_from(settings, "max_concurrent_limit", MAX_CONCURRENT_LIMIT)))
    MAX_CONCURRENT = max(1, min(MAX_CONCURRENT_LIMIT, get_int_from(settings, "max_concurrent", MAX_CONCURRENT)))
    TIMEOUT = normalize_timeout(settings.get("timeout"), TIMEOUT)
    DETECT_TIMEOUT = normalize_timeout(settings.get("detect_timeout"), DETECT_TIMEOUT)
    AUTH_SESSION_DAYS = max(1, min(365, get_int_from(settings, "auth_session_days", AUTH_SESSION_DAYS)))
    AUTH_SESSION_SECONDS = AUTH_SESSION_DAYS * 86400
    LOG_LIMIT = max(20, min(1000, get_int_from(settings, "log_limit", LOG_LIMIT)))
    set_log_limit(LOG_LIMIT)
    APP_TIMEZONE = normalize_timezone(settings.get("timezone", APP_TIMEZONE))
    new_password = str(settings.get("auth_password") or "").strip()
    password_changed = False
    if new_password and "AUTH_PASSWORD" not in os.environ and new_password != AUTH_PASSWORD:
        AUTH_PASSWORD = new_password
        if "AUTH_SESSION_SECRET" not in os.environ:
            AUTH_SESSION_SECRET = AUTH_PASSWORD
        password_changed = True
    check_engine = ProxyCheckEngine(
        CheckConfig(
            timeout=TIMEOUT,
            detect_timeout=DETECT_TIMEOUT,
            check_rounds=CHECK_ROUNDS,
        )
    )
    return password_changed


def get_int_from(data, key, default):
    try:
        return int(data.get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default


def save_runtime_settings(settings):
    local_config = read_local_config()
    password_changed = apply_runtime_settings(settings)
    local_config.update({
        "check_rounds": CHECK_ROUNDS,
        "max_check_rounds": MAX_CHECK_ROUNDS,
        "max_concurrent": MAX_CONCURRENT,
        "max_concurrent_limit": MAX_CONCURRENT_LIMIT,
        "timeout": TIMEOUT,
        "detect_timeout": DETECT_TIMEOUT,
        "auth_session_days": AUTH_SESSION_DAYS,
        "log_limit": LOG_LIMIT,
        "timezone": APP_TIMEZONE,
    })
    if password_changed:
        local_config["auth_password"] = AUTH_PASSWORD
    write_local_config(local_config)
    return password_changed

# ============================================================
# Session cleanup
# ============================================================
def cleanup_sessions():
    while True:
        time.sleep(120)
        now = time.time()
        with sessions_lock:
            to_del = [k for k, v in sessions.items()
                      if v.get("finished") and now - v.get("created", now) > 600]
            for k in to_del:
                del sessions[k]
            if to_del:
                log.info(f"Cleaned up {len(to_del)} stale sessions, {len(sessions)} remaining")

threading.Thread(target=cleanup_sessions, daemon=True).start()

# ============================================================
# Auto Mode Scheduler
# ============================================================
def list_auto_tokens():
    tokens = []
    if not os.path.isdir(AUTO_DIR):
        return tokens
    for name in os.listdir(AUTO_DIR):
        if name.endswith(".json"):
            tokens.append(sanitize_token(name[:-5]))
    return tokens


def load_auto_record(token):
    token = sanitize_token(token)
    data = read_json_file(auto_json_path(token), {})
    config = normalize_auto_config(data.get("config") if isinstance(data, dict) else {})
    state = default_auto_state(config)
    if isinstance(data, dict) and isinstance(data.get("state"), dict):
        state.update(data["state"])
    history = state.get("history")
    state["history"] = history[-20:] if isinstance(history, list) else []
    if not config.get("enabled"):
        state["status"] = "disabled"
        state["next_run_at"] = None
    elif state.get("next_run_at") is None and not state.get("running"):
        state["next_run_at"] = compute_next_run(config)
    return {"config": config, "state": state}


def save_auto_record(token, record):
    token = sanitize_token(token)
    config = normalize_auto_config(record.get("config", {}))
    state = record.get("state") if isinstance(record.get("state"), dict) else default_auto_state(config)
    history = state.get("history")
    state["history"] = history[-20:] if isinstance(history, list) else []
    atomic_write_json(auto_json_path(token), {"config": config, "state": state})
    return {"config": config, "state": state}


def append_auto_history(state, summary):
    history = state.get("history")
    if not isinstance(history, list):
        history = []
    history.append(summary)
    state["history"] = history[-20:]
    state["last_summary"] = summary


def runtime_counts(results):
    valid = sum(1 for r in results if r.get("valid"))
    unstable = sum(1 for r in results if r.get("unstable"))
    invalid = sum(1 for r in results if not r.get("valid") and not r.get("unstable"))
    return valid, unstable, invalid


def get_auto_status(token, since=0, client_session_id=""):
    token = sanitize_token(token)
    with auto_lock:
        record = load_auto_record(token)
        config = normalize_auto_config(record.get("config", {}))
        runtime = auto_runtime.get(token)
        new_results = []
        results_index = 0
        if runtime:
            results = runtime.get("results", [])
            try:
                since = int(since)
            except (TypeError, ValueError):
                since = 0
            if client_session_id and client_session_id != runtime.get("run_id"):
                since = 0
            since = max(0, min(len(results), since))
            new_results = results[since:]
            results_index = len(results)
            valid, unstable, invalid = runtime_counts(results)
            record["state"].update({
                "running": True,
                "status": runtime.get("status", "running"),
                "session_id": runtime.get("run_id"),
                "stage": runtime.get("stage", "running"),
                "started_at": runtime.get("started_at"),
                "total": runtime.get("total", 0),
                "done": runtime.get("done", 0),
                "valid_count": valid,
                "unstable_count": unstable,
                "invalid_count": invalid,
                "source_count": runtime.get("source_count", 0),
                "repo_count": runtime.get("repo_count", 0),
                "input_count": runtime.get("input_count", 0),
                "skipped": runtime.get("skipped", 0),
                "error": runtime.get("error"),
            })
        else:
            stopped = auto_stopped_results.get(token)
            if stopped and stopped.get("expires", 0) < time.time():
                del auto_stopped_results[token]
                stopped = None
            if stopped:
                results = stopped.get("results", [])
                try:
                    since = int(since)
                except (TypeError, ValueError):
                    since = 0
                if client_session_id and client_session_id != stopped.get("run_id"):
                    since = 0
                since = max(0, min(len(results), since))
                new_results = results[since:]
                results_index = len(results)
        state = record["state"]
        state["next_run_text"] = format_timestamp(state.get("next_run_at"), config.get("timezone"))
        state["started_text"] = format_timestamp(state.get("started_at"), config.get("timezone"))
        state["finished_text"] = format_timestamp(state.get("finished_at"), config.get("timezone"))
        record["config"] = config
        record["server_time"] = server_time_payload(config.get("timezone"))
        record["auto_mode"] = True
        record["new"] = new_results
        record["results_index"] = results_index
        return record


def is_auto_running(token):
    token = sanitize_token(token)
    with auto_lock:
        runtime = auto_runtime.get(token)
        return bool(runtime and not runtime.get("finished"))


def update_auto_runtime(token, **fields):
    token = sanitize_token(token)
    with auto_lock:
        runtime = auto_runtime.get(token)
        if runtime:
            runtime.update(fields)
        record = load_auto_record(token)
        state = record["state"]
        if "stage" in fields:
            state["stage"] = fields["stage"]
        if "status" in fields:
            state["status"] = fields["status"]
        for key in ("total", "done", "source_count", "repo_count", "input_count", "skipped", "error"):
            if key in fields:
                state[key] = fields[key]
        save_auto_record(token, record)


def result_repo_key(result):
    return proxy_key(result.get("original") or result.get("proxy"))


def result_to_repo_item(result, existing=None):
    now = int(time.time() * 1000)
    existing = existing or {}
    country = result.get("country")
    checks_detail = result.get("checks_detail")
    if not country and isinstance(checks_detail, dict):
        ip_info = checks_detail.get("ip_info")
        if isinstance(ip_info, dict):
            country = ip_info.get("country")
    item = {
        "proxy": result.get("proxy") or result.get("original"),
        "grade": result.get("grade") or "F",
        "latency": result.get("latency"),
        "ip": result.get("ip"),
        "country": str(country).upper() if country else None,
        "ip_type": result.get("ip_type"),
        "service_reachable": result.get("service_reachable") is True,
        "api_reachable": result.get("api_reachable") is True,
        "cf_bypass": result.get("cf_bypass") is True,
        "recommended_use": result.get("recommended_use"),
        "target_profile": result.get("target_profile"),
        "target_name": result.get("target_name"),
        "added": existing.get("added") or now,
        "updated": now,
    }
    return compact_repo_item(item)


def result_matches_policy(result, policy):
    grade = str(result.get("grade") or "F").upper()
    if policy == "archive_all":
        return True
    if policy == "grade_a_only":
        return grade == "A"
    if policy == "grade_b_only":
        return grade == "B"
    if policy == "grade_ab_only":
        return grade in ("A", "B")
    if policy == "include_unstable":
        return grade in ("A", "B", "C", "D") or result.get("valid") or result.get("unstable")
    return grade in ("A", "B", "C") or result.get("valid")


def merge_repo_results(token, repo, results, checked_inputs, policy):
    policy = policy if policy in REPO_UPDATE_POLICIES else "stable_only"
    participating = {proxy_key(proxy) for proxy in checked_inputs}
    result_by_key = {}
    for result in results:
        for value in (result.get("original"), result.get("proxy")):
            key = proxy_key(value)
            if key:
                result_by_key[key] = result

    existing_by_key = {}
    for item in compact_repo(repo):
        existing_by_key[proxy_key(item["proxy"])] = item

    removed = 0
    next_repo = []
    used_old_keys = set()
    for item in compact_repo(repo):
        key = proxy_key(item["proxy"])
        result = result_by_key.get(key)
        if policy != "archive_all" and key in participating and result and not result_matches_policy(result, policy):
            removed += 1
            used_old_keys.add(key)
            continue
        next_repo.append(item)

    index_by_key = {proxy_key(item["proxy"]): i for i, item in enumerate(next_repo)}
    added = 0
    updated = 0
    for result in results:
        if not result_matches_policy(result, policy):
            continue
        candidate_keys = [proxy_key(result.get("original")), proxy_key(result.get("proxy"))]
        existing = None
        existing_index = None
        for key in candidate_keys:
            if key in index_by_key:
                existing_index = index_by_key[key]
                existing = next_repo[existing_index]
                break
            if key in existing_by_key:
                existing = existing_by_key[key]
        item = result_to_repo_item(result, existing)
        if not item:
            continue
        if existing_index is None:
            next_repo.append(item)
            index_by_key[proxy_key(item["proxy"])] = len(next_repo) - 1
            added += 1
        else:
            next_repo[existing_index] = item
            index_by_key[proxy_key(item["proxy"])] = existing_index
            updated += 1

    saved = write_repo_data(token, next_repo)
    return {
        "repo_count": len(saved),
        "repo_added": added,
        "repo_updated": updated,
        "repo_removed": removed,
    }


def build_auto_summary(runtime, status, error=None, repo_summary=None):
    results = runtime.get("results", [])
    valid, unstable, invalid = runtime_counts(results)
    started_at = runtime.get("started_at") or time.time()
    finished_at = time.time()
    summary = {
        "status": status,
        "reason": runtime.get("reason", "schedule"),
        "started_at": int(started_at),
        "finished_at": int(finished_at),
        "duration_seconds": max(0, int(finished_at - started_at)),
        "target_profile": runtime.get("target_profile", "generic"),
        "rounds": runtime.get("rounds", CHECK_ROUNDS),
        "max_concurrent": runtime.get("max_concurrent", MAX_CONCURRENT),
        "detect_mode": runtime.get("detect_mode", "skip"),
        "repo_update_policy": runtime.get("repo_update_policy", "stable_only"),
        "schedule_type": runtime.get("schedule_type"),
        "interval_hours": runtime.get("interval_hours"),
        "daily_time": runtime.get("daily_time"),
        "timezone": runtime.get("timezone", APP_TIMEZONE),
        "source_count": runtime.get("source_count", 0),
        "repo_input_count": runtime.get("repo_count", 0),
        "input_count": runtime.get("input_count", 0),
        "skipped": runtime.get("skipped", 0),
        "total": runtime.get("total", 0),
        "done": runtime.get("done", 0),
        "valid_count": valid,
        "unstable_count": unstable,
        "invalid_count": invalid,
    }
    if error:
        summary["error"] = str(error)[:300]
    if repo_summary:
        summary.update(repo_summary)
    return summary


def finalize_auto_run(token, runtime, status, error=None, repo_summary=None):
    token = sanitize_token(token)
    summary = build_auto_summary(runtime, status, error, repo_summary)
    with auto_lock:
        record = load_auto_record(token)
        config = normalize_auto_config(record.get("config", {}))
        state = record["state"]
        state.update({
            "running": False,
            "status": status,
            "session_id": None,
            "stage": status,
            "finished_at": summary["finished_at"],
            "last_run_at": summary["finished_at"],
            "next_run_at": compute_next_run(config) if config.get("enabled") else None,
            "error": summary.get("error"),
        })
        append_auto_history(state, summary)
        save_auto_record(token, {"config": config, "state": state})
        if status == "stopped":
            auto_stopped_results[token] = {
                "run_id": runtime.get("run_id"),
                "results": list(runtime.get("results", [])),
                "expires": time.time() + 900,
            }
        else:
            auto_stopped_results.pop(token, None)
        stored = auto_runtime.get(token)
        if stored and stored.get("run_id") == runtime.get("run_id"):
            stored["finished"] = True
            del auto_runtime[token]
    finish_log(token, runtime.get("log_id") or runtime.get("run_id"), {
        **summary,
        "type": "auto",
        "status": status,
        "session_id": runtime.get("run_id"),
        "target_name": get_target_profile_name(summary.get("target_profile")),
    })
    log.info("Auto run finished", extra={"token": token, "status": status, "summary": summary})


def execute_auto_run(token, config, run_id, reason):
    token = sanitize_token(token)
    runtime = None
    try:
        with auto_lock:
            runtime = auto_runtime[token]
        update_auto_runtime(token, stage="fetching", status="running")
        if not FETCH_PROXIES_AVAILABLE:
            raise RuntimeError("fetch_proxies 模块不可用")
        fetched, _source_name, err = fetch_proxies("all", 50000)
        if err:
            raise RuntimeError(err)
        source_proxies = normalize_proxy_list(fetched)

        update_auto_runtime(token, stage="loading_repo", source_count=len(source_proxies))
        repo = read_repo_data(token)
        repo_proxies = normalize_proxy_list(item.get("proxy") for item in repo)
        combined = normalize_proxy_list(source_proxies + repo_proxies)

        checked = read_checked_list(token)
        checked_keys = {proxy_key(proxy) for proxy in checked}
        if config["detect_mode"] == "skip":
            to_check = [proxy for proxy in combined if proxy_key(proxy) not in checked_keys]
        else:
            to_check = combined
        skipped = len(combined) - len(to_check)
        with auto_lock:
            runtime.update({
                "target_profile": config["target_profile"],
                "rounds": config["rounds"],
                "max_concurrent": config["max_concurrent"],
                "detect_mode": config["detect_mode"],
                "repo_update_policy": config["repo_update_policy"],
                "repo_count": len(repo),
                "input_count": len(combined),
                "total": len(to_check),
                "skipped": skipped,
            })
        update_auto_runtime(token, stage="detecting", repo_count=len(repo), total=len(to_check), skipped=skipped)

        if to_check:
            async def run_async():
                await check_engine.check_many_async(
                    proxies=to_check,
                    stop_event=runtime["stop"],
                    rounds=config["rounds"],
                    max_concurrent=config["max_concurrent"],
                    on_result=lambda result: publish_auto_result(token, result),
                    target_profile=config["target_profile"],
                )

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(run_async())
            finally:
                loop.close()

        if runtime["stop"].is_set():
            finalize_auto_run(token, runtime, "stopped")
            return

        update_auto_runtime(token, stage="updating_repo")
        detected = [result.get("original") or result.get("proxy") for result in runtime.get("results", [])]
        append_checked_list(token, detected)
        repo_summary = merge_repo_results(
            token=token,
            repo=repo,
            results=runtime.get("results", []),
            checked_inputs=to_check,
            policy=config["repo_update_policy"],
        )
        finalize_auto_run(token, runtime, "completed", repo_summary=repo_summary)
    except Exception as exc:
        if runtime is None:
            runtime = {
                "run_id": run_id,
                "reason": reason,
                "started_at": time.time(),
                "results": [],
                "done": 0,
                "total": 0,
                "target_profile": config.get("target_profile", "generic"),
                "rounds": config.get("rounds", CHECK_ROUNDS),
                "max_concurrent": config.get("max_concurrent", MAX_CONCURRENT),
                "detect_mode": config.get("detect_mode", "skip"),
                "repo_update_policy": config.get("repo_update_policy", "stable_only"),
            }
        log.error("Auto run failed", extra={"token": token, "error": str(exc)}, exc_info=True)
        finalize_auto_run(token, runtime, "failed", error=exc)


def publish_auto_result(token, result):
    if not result:
        return
    token = sanitize_token(token)
    with auto_lock:
        runtime = auto_runtime.get(token)
        if not runtime:
            return
        runtime["results"].append(result)
        runtime["done"] = runtime.get("done", 0) + 1


def start_auto_run(token, reason="schedule"):
    token = sanitize_token(token)
    with auto_lock:
        if token in auto_runtime:
            return False, "自动任务正在执行"
        record = load_auto_record(token)
        config = normalize_auto_config(record.get("config", {}))
        if reason == "schedule" and not config.get("enabled"):
            return False, "自动任务未启用"
        run_id = f"auto_{int(time.time())}_{id(config)}"
        started_at = time.time()
        log_id = start_log(token, {
            "id": run_id,
            "type": "auto",
            "status": "running",
            "session_id": run_id,
            "reason": reason,
            "started_at": int(started_at),
            "target_profile": config["target_profile"],
            "target_name": get_target_profile_name(config["target_profile"]),
            "rounds": config["rounds"],
            "max_concurrent": config["max_concurrent"],
            "detect_mode": config["detect_mode"],
            "repo_update_policy": config["repo_update_policy"],
            "schedule_type": config["schedule_type"],
            "interval_hours": config["interval_hours"],
            "daily_time": config["daily_time"],
            "timezone": config["timezone"],
        })
        runtime = {
            "run_id": run_id,
            "log_id": log_id,
            "reason": reason,
            "stop": threading.Event(),
            "status": "running",
            "stage": "starting",
            "started_at": started_at,
            "results": [],
            "done": 0,
            "total": 0,
            "finished": False,
            "target_profile": config["target_profile"],
            "rounds": config["rounds"],
            "max_concurrent": config["max_concurrent"],
            "detect_mode": config["detect_mode"],
            "repo_update_policy": config["repo_update_policy"],
            "schedule_type": config["schedule_type"],
            "interval_hours": config["interval_hours"],
            "daily_time": config["daily_time"],
            "timezone": config["timezone"],
        }
        auto_runtime[token] = runtime
        state = record["state"]
        state.update({
            "running": True,
            "status": "running",
            "session_id": run_id,
            "stage": "starting",
            "started_at": int(runtime["started_at"]),
            "finished_at": None,
            "next_run_at": compute_next_run(config, runtime["started_at"]) if config.get("enabled") else None,
            "error": None,
        })
        save_auto_record(token, {"config": config, "state": state})

    thread = threading.Thread(target=execute_auto_run, args=(token, config, run_id, reason), daemon=True)
    with auto_lock:
        if token in auto_runtime:
            auto_runtime[token]["thread"] = thread
    thread.start()
    return True, run_id


def stop_auto_run(token):
    token = sanitize_token(token)
    with auto_lock:
        runtime = auto_runtime.get(token)
        if not runtime:
            return False
        runtime["status"] = "stopping"
        runtime["stage"] = "stopping"
        runtime["stop"].set()
        record = load_auto_record(token)
        record["state"]["status"] = "stopping"
        record["state"]["stage"] = "stopping"
        save_auto_record(token, record)
    return True


def save_auto_config(token, config):
    token = sanitize_token(token)
    with auto_lock:
        record = load_auto_record(token)
        normalized = normalize_auto_config(config)
        state = record["state"]
        if normalized.get("enabled"):
            state["status"] = "running" if token in auto_runtime else "idle"
            if token not in auto_runtime:
                state["next_run_at"] = compute_next_run(normalized)
        else:
            state["status"] = "disabled"
            state["next_run_at"] = None
        state["running"] = token in auto_runtime
        state["stage"] = "running" if token in auto_runtime else state["status"]
        return save_auto_record(token, {"config": normalized, "state": state})


def mark_interrupted_auto_runs():
    now = int(time.time())
    for token in list_auto_tokens():
        with auto_lock:
            record = load_auto_record(token)
            config = normalize_auto_config(record.get("config", {}))
            state = record["state"]
            if not state.get("running"):
                continue
            summary = {
                "status": "interrupted",
                "reason": "service_restart",
                "started_at": state.get("started_at"),
                "finished_at": now,
                "duration_seconds": 0,
                "target_profile": config.get("target_profile", "generic"),
                "rounds": config.get("rounds", CHECK_ROUNDS),
                "max_concurrent": config.get("max_concurrent", MAX_CONCURRENT),
                "detect_mode": config.get("detect_mode", "skip"),
                "repo_update_policy": config.get("repo_update_policy", "stable_only"),
                "error": "服务重启，上一轮自动任务已中断",
            }
            state.update({
                "running": False,
                "status": "interrupted",
                "stage": "interrupted",
                "session_id": None,
                "finished_at": now,
                "next_run_at": now if config.get("enabled") else None,
                "error": summary["error"],
            })
            append_auto_history(state, summary)
            save_auto_record(token, {"config": config, "state": state})


def scheduler_loop():
    while True:
        due_tokens = []
        now = time.time()
        for token in list_auto_tokens():
            with auto_lock:
                record = load_auto_record(token)
                config = normalize_auto_config(record.get("config", {}))
                state = record["state"]
                if not config.get("enabled") or token in auto_runtime:
                    continue
                next_run_at = state.get("next_run_at")
                if next_run_at is None:
                    state["next_run_at"] = compute_next_run(config, now)
                    save_auto_record(token, {"config": config, "state": state})
                    continue
                try:
                    due = float(next_run_at) <= now
                except (TypeError, ValueError):
                    due = True
                if due:
                    due_tokens.append(token)
        for token in due_tokens:
            started, message = start_auto_run(token, "schedule")
            if started:
                log.info("Scheduled auto run started", extra={"token": token})
            else:
                log.warning("Scheduled auto run skipped", extra={"token": token, "message": message})
        time.sleep(30)


def start_auto_scheduler():
    mark_interrupted_auto_runs()
    threading.Thread(target=scheduler_loop, daemon=True).start()

# ============================================================
# Deep Check (optional, requires nodriver + Chrome)
# ============================================================
async def deep_check_nodriver(proxy_str, target_url, timeout=20):
    """
    Use nodriver (real browser) to verify proxy can bypass CF.
    Returns: (success, details)
    """
    if not NODRIVER_AVAILABLE:
        return False, {"error": "nodriver not installed"}

    browser = None
    try:
        # Configure nodriver with proxy
        config = nodriver.Config()
        config.add_argument(f"--proxy-server={proxy_str}")
        config.add_argument("--no-sandbox")
        config.add_argument("--disable-dev-shm-usage")
        config.headless = True

        browser = await nodriver.start(config=config)
        page = await browser.get(target_url)

        # Wait for page to load
        await asyncio.sleep(5)

        # Check page content
        title = await page.evaluate("document.title")
        body_text = await page.evaluate("document.body.innerText.substring(0, 2000)")

        # Check for CF challenge
        cf_detected = False
        cf_type = None
        for indicator in ["Just a moment", "Checking your browser", "Verify you are human", "challenge-platform"]:
            if indicator.lower() in body_text.lower():
                cf_detected = True
                if "turnstile" in body_text.lower():
                    cf_type = "turnstile"
                elif "just a moment" in body_text.lower():
                    cf_type = "js"
                else:
                    cf_type = "managed"
                break

        has_content = any(kw in body_text.lower() for kw in ["chatgpt", "chat.openai.com", "log in", "sign up"])

        return True, {
            "title": title,
            "body_preview": body_text[:500],
            "cf_detected": cf_detected,
            "cf_type": cf_type,
            "has_real_content": has_content,
            "success": has_content and not cf_detected,
        }

    except Exception as e:
        return False, {"error": str(e)[:200]}
    finally:
        if browser:
            try:
                await browser.stop()
            except Exception:
                pass

def run_deep_check(proxy_str, target_url=None):
    """Synchronous wrapper for deep check."""
    if not NODRIVER_AVAILABLE:
        return {"error": "nodriver not installed", "success": False}

    target = target_url or TARGET_CHAT
    loop = asyncio.new_event_loop()
    try:
        ok, details = loop.run_until_complete(
            deep_check_nodriver(proxy_str, target, timeout=20)
        )
        return {"success": ok, **details}
    finally:
        loop.close()

# ============================================================
# Main Check Runner
# ============================================================
def run_check(session_id, proxies, rounds=None, target_profile=None, max_concurrent=None, token="default"):
    if rounds is None:
        rounds = CHECK_ROUNDS
    rounds = normalize_rounds(rounds)
    target_profile = normalize_target_profile(target_profile)
    max_concurrent = normalize_max_concurrent(max_concurrent)
    token = sanitize_token(token)
    with sessions_lock:
        sessions[session_id]["stop"] = threading.Event()
    stop_event = sessions[session_id]["stop"]

    def publish_result(result):
        if result:
            with sessions_lock:
                s = sessions.get(session_id)
                if s:
                    s["results"].append(result)
                    s["done"] += 1

    async def run_async():
        await check_engine.check_many_async(
            proxies=proxies,
            stop_event=stop_event,
            rounds=rounds,
            max_concurrent=max_concurrent,
            on_result=publish_result,
            target_profile=target_profile,
        )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_async())
    finally:
        loop.close()

    with sessions_lock:
        s = sessions.get(session_id)
        if s:
            s["finished"] = True
            results = list(s.get("results", []))
            valid, unstable, invalid = runtime_counts(results)
            status = "stopped" if stop_event.is_set() else "completed"
            finish_log(token, s.get("log_id") or session_id, {
                "type": "manual",
                "status": status,
                "session_id": session_id,
                "finished_at": int(time.time()),
                "target_profile": target_profile,
                "target_name": get_target_profile_name(target_profile),
                "rounds": rounds,
                "max_concurrent": max_concurrent,
                "total": s.get("total", len(proxies)),
                "done": s.get("done", len(results)),
                "valid_count": valid,
                "unstable_count": unstable,
                "invalid_count": invalid,
            })

# ============================================================
# Proxy Gateway
# ============================================================
class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    daemon_threads = True
    allow_reuse_address = True


class ProxyGatewayHandler(StreamRequestHandler):
    timeout = PROXY_GATEWAY_TIMEOUT

    def handle(self):
        try:
            request_line = self.rfile.readline(65536)
            if not request_line:
                return
            headers = self._read_headers()
            parts = request_line.decode("iso-8859-1", errors="replace").strip().split()
            if len(parts) < 3:
                self._send_gateway_error(400, "Bad Request")
                return
            method, target, version = parts[0].upper(), parts[1], parts[2]
            if method == "CONNECT":
                self._handle_connect(target, version, headers)
            else:
                self._handle_http(method, target, version, headers)
        except Exception as exc:
            log.warning("Proxy gateway request failed", extra={"error": str(exc)})

    def _read_headers(self):
        headers = []
        while True:
            line = self.rfile.readline(65536)
            if not line or line in (b"\r\n", b"\n"):
                break
            headers.append(line)
        return headers

    def _headers_to_dict(self, headers):
        out = {}
        for raw in headers:
            text = raw.decode("iso-8859-1", errors="replace")
            if ":" not in text:
                continue
            key, value = text.split(":", 1)
            out[key.strip().lower()] = value.strip()
        return out

    def _send_gateway_error(self, code, reason):
        body = f"{code} {reason}\n".encode("utf-8")
        response = (
            f"HTTP/1.1 {code} {reason}\r\n"
            "Connection: close\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
        ).encode("ascii") + body
        try:
            self.wfile.write(response)
        except Exception:
            pass

    def _open_upstream(self, upstream):
        sock = socket.create_connection((upstream["host"], upstream["port"]), timeout=PROXY_GATEWAY_TIMEOUT)
        sock.settimeout(PROXY_GATEWAY_TIMEOUT)
        if upstream["scheme"] == "https":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=upstream["host"])
            sock.settimeout(PROXY_GATEWAY_TIMEOUT)
        return sock

    def _read_upstream_headers(self, sock):
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data

    def _connect_via_upstream(self, upstream, target):
        sock = self._open_upstream(upstream)
        request = (
            f"CONNECT {target} HTTP/1.1\r\n"
            f"Host: {target}\r\n"
            "Proxy-Connection: keep-alive\r\n"
            f"{upstream['auth']}"
            "\r\n"
        ).encode("iso-8859-1")
        sock.sendall(request)
        response = self._read_upstream_headers(sock)
        first_line = response.split(b"\r\n", 1)[0]
        if b" 200 " not in first_line:
            try:
                sock.close()
            except Exception:
                pass
            return None, response or first_line
        return sock, response

    def _relay(self, sock):
        sockets = [self.connection, sock]
        for item in sockets:
            item.setblocking(False)
        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, PROXY_GATEWAY_TIMEOUT)
                if exceptional or not readable:
                    break
                for source in readable:
                    try:
                        chunk = source.recv(65536)
                    except (BlockingIOError, InterruptedError):
                        continue
                    if not chunk:
                        return
                    target = sock if source is self.connection else self.connection
                    target.sendall(chunk)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_connect(self, target, version, headers):
        if ":" not in target:
            target = f"{target}:443"
        last_error = None
        for upstream in ordered_proxy_gateway_candidates():
            try:
                sock, response = self._connect_via_upstream(upstream, target)
                if sock:
                    self.wfile.write(response)
                    self._relay(sock)
                    return
                last_error = response.decode("iso-8859-1", errors="replace").splitlines()[0] if response else "upstream rejected CONNECT"
            except Exception as exc:
                last_error = str(exc)
        log.warning("Proxy gateway CONNECT failed", extra={"target": target, "error": last_error})
        self._send_gateway_error(502, "No Available Upstream Proxy")

    def _handle_http(self, method, target, version, headers):
        header_map = self._headers_to_dict(headers)
        host = header_map.get("host")
        if not target.startswith(("http://", "https://")):
            if not host:
                self._send_gateway_error(400, "Missing Host Header")
                return
            target = f"http://{host}{target}"

        body = b""
        try:
            content_length = int(header_map.get("content-length", "0"))
        except ValueError:
            content_length = 0
        if content_length > 0:
            body = self.rfile.read(content_length)

        filtered_headers = []
        for line in headers:
            lower = line.decode("iso-8859-1", errors="replace").split(":", 1)[0].strip().lower()
            if lower in ("connection", "proxy-authorization", "proxy-connection"):
                continue
            filtered_headers.append(line)

        request_head = (
            f"{method} {target} {version}\r\n"
            + b"".join(filtered_headers).decode("iso-8859-1", errors="replace")
            + "Connection: close\r\n"
        )

        last_error = None
        for upstream in ordered_proxy_gateway_candidates():
            try:
                sock = self._open_upstream(upstream)
                payload = request_head + upstream["auth"] + "\r\n"
                sock.sendall(payload.encode("iso-8859-1") + body)
                self._relay(sock)
                return
            except Exception as exc:
                last_error = str(exc)
                try:
                    sock.close()
                except Exception:
                    pass
        log.warning("Proxy gateway HTTP failed", extra={"target": target, "error": last_error})
        self._send_gateway_error(502, "No Available Upstream Proxy")


def start_proxy_gateway():
    if not PROXY_GATEWAY_ENABLED:
        log.info("Proxy gateway disabled")
        return None
    if PROXY_GATEWAY_PORT <= 0:
        log.info("Proxy gateway disabled by port")
        return None
    try:
        server = ThreadingTCPServer((PROXY_GATEWAY_BIND, PROXY_GATEWAY_PORT), ProxyGatewayHandler)
    except Exception as exc:
        log.error("Proxy gateway failed to start", extra={"bind": PROXY_GATEWAY_BIND, "port": PROXY_GATEWAY_PORT, "error": str(exc)})
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info(
        f"Proxy gateway running at http://{PROXY_GATEWAY_BIND}:{PROXY_GATEWAY_PORT} "
        f"with grades {','.join(sorted(proxy_gateway_grade_set()))}"
    )
    return server

# ============================================================
# HTTP Server
# ============================================================
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc_type, exc, _ = sys.exc_info()
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            log.warning("Client disconnected early", extra={"client_address": client_address})
            return
        super().handle_error(request, client_address)

from http.server import SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        # Serve repo as txt: /api/repo/<token>.txt
        # Serve repo as JSON: /api/repo/<token>.json
        if path.startswith("/api/repo/") and path.endswith(".json"):
            token = path.split("/")[-1].replace(".json", "")
            json_file = os.path.join(REPO_DIR, f"{token}.json")
            if os.path.isfile(json_file):
                with open(json_file, "r") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"[]")
            return

        # Serve repo as txt: /api/repo/<token>.txt
        if path.startswith("/api/repo/") and path.endswith(".txt"):
            token = path.split("/")[-1].replace(".txt", "")
            repo_file = os.path.join(REPO_DIR, f"{token}.txt")
            if os.path.isfile(repo_file):
                with open(repo_file, "r") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Repository not found")
            return
        # Serve checked proxies as txt: /api/checked/<token>.txt
        if path.startswith("/api/checked/") and path.endswith(".txt"):
            token = path.split("/")[-1].replace(".txt", "")
            checked_file = checked_txt_path(token)
            if os.path.isfile(checked_file):
                with open(checked_file, "r") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"")
            return

        if path == "/login.html":
            self._send_static_file("login.html")
            return

        if path in ("/", "/index.html") and is_auth_enabled() and not is_request_authenticated(self.headers):
            self._send_static_file("login.html")
            return

        if path == "/app.js" and is_auth_enabled() and not is_request_authenticated(self.headers):
            self._json(401, {"error": "请先输入登录密码", "auth_required": True})
            return

        static_files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
        }
        file_name = static_files.get(path)
        if file_name is None:
            self.send_response(404); self.end_headers(); return
        self._send_static_file(file_name)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            if self.path == "/api/auth/status":
                self._json(200, {
                    "authenticated": is_request_authenticated(self.headers),
                    "auth_required": is_auth_enabled(),
                })

            elif self.path == "/api/auth/login":
                password = str(body.get("password", ""))
                if not hmac.compare_digest(password, AUTH_PASSWORD):
                    self._json(401, {"error": "密码不正确", "auth_required": True})
                    return
                token = make_auth_token()
                self._json(200, {
                    "ok": True,
                    "token": token,
                    "expires_in": AUTH_SESSION_SECONDS,
                    "auth_required": is_auth_enabled(),
                }, [("Set-Cookie", make_auth_cookie(token))])

            elif self.path == "/api/auth/logout":
                self._json(200, {"ok": True}, [("Set-Cookie", make_auth_cookie("", 0))])

            elif self.path == "/api/capabilities":
                # Return server capabilities
                self._json(200, {
                    "nodriver": NODRIVER_AVAILABLE,
                    "xvfb": XVFB_AVAILABLE,
                    "deep_check": NODRIVER_AVAILABLE,
                    "fetch_proxies": FETCH_PROXIES_AVAILABLE,
                    "target_profiles": list(TARGET_PROFILE_OPTIONS),
                    "max_concurrent": MAX_CONCURRENT,
                    "max_concurrent_limit": MAX_CONCURRENT_LIMIT,
                    "auth_required": is_auth_enabled(),
                    "authenticated": is_request_authenticated(self.headers),
                    "auto_mode": True,
                    "auto_mode_hint": "后台自动任务仅在自托管 Python 服务中可用",
                    "settings": public_settings_payload(),
                    "proxy_sources": [{"id": s["id"], "name": s["name"]} for s in (PROXY_SOURCES if FETCH_PROXIES_AVAILABLE else [])],
                })

            elif not is_request_authenticated(self.headers):
                self._json(401, {"error": "请先输入登录密码", "auth_required": True})

            elif self.path == "/api/settings/get":
                self._json(200, {"settings": public_settings_payload(), "server_time": server_time_payload(APP_TIMEZONE)})

            elif self.path == "/api/settings/save":
                settings = body.get("settings", {})
                password_changed = save_runtime_settings(settings)
                response = {"ok": True, "settings": public_settings_payload(), "password_changed": password_changed}
                if password_changed:
                    token = make_auth_token()
                    response["token"] = token
                    response["expires_in"] = AUTH_SESSION_SECONDS
                    self._json(200, response, [("Set-Cookie", make_auth_cookie(token))])
                else:
                    self._json(200, response)

            elif self.path == "/api/logs/list":
                token = sanitize_token(body.get("token", "default"))
                self._json(200, logs_payload(token))

            elif self.path == "/api/logs/clear":
                token = sanitize_token(body.get("token", "default"))
                clear_logs(token)
                self._json(200, {"ok": True, **logs_payload(token)})

            elif self.path == "/api/start":
                proxies = body.get("proxies", [])
                rounds = normalize_rounds(body.get("rounds", CHECK_ROUNDS))
                target_profile = normalize_target_profile(body.get("target_profile", "generic"))
                max_concurrent = normalize_max_concurrent(body.get("max_concurrent", MAX_CONCURRENT))
                token = sanitize_token(body.get("token", ""))
                if body.get("token") and is_auto_running(token):
                    self._json(200, {"error": "自动任务正在执行，请先停止自动任务", "auto_running": True})
                    return
                sid = str(time.time()) + str(id(proxies))
                log_id = start_log(token, {
                    "id": sid,
                    "type": "manual",
                    "status": "running",
                    "session_id": sid,
                    "started_at": int(time.time()),
                    "target_profile": target_profile,
                    "target_name": get_target_profile_name(target_profile),
                    "rounds": rounds,
                    "max_concurrent": max_concurrent,
                    "total": len(proxies),
                    "timezone": APP_TIMEZONE,
                })
                with sessions_lock:
                    sessions[sid] = {
                        "results": [], "done": 0, "finished": False,
                        "stop": None, "total": len(proxies), "created": time.time(),
                        "rounds": rounds, "target_profile": target_profile,
                        "max_concurrent": max_concurrent, "token": token,
                        "log_id": log_id,
                    }
                threading.Thread(target=run_check, args=(sid, proxies, rounds, target_profile, max_concurrent, token), daemon=True).start()
                log.info(f"Start check: session={sid}, proxies={len(proxies)}, rounds={rounds}, target_profile={target_profile}, max_concurrent={max_concurrent}")
                self._json(200, {"session_id": sid, "total": len(proxies), "rounds": rounds, "target_profile": target_profile, "max_concurrent": max_concurrent})

            elif self.path == "/api/status":
                sid = body.get("session_id", "")
                since = body.get("since", 0)
                with sessions_lock:
                    s = sessions.get(sid)
                    if not s:
                        self._json(200, {"error": "not found"}); return
                    all_r = s["results"]
                    new_r = all_r[since:]
                    self._json(200, {
                        "new": new_r,
                        "total_done": s["done"],
                        "total": s["total"],
                        "finished": s["finished"],
                        "target_profile": s.get("target_profile", "generic"),
                        "max_concurrent": s.get("max_concurrent", MAX_CONCURRENT),
                        "valid_count": sum(1 for r in all_r if r.get("valid")),
                        "unstable_count": sum(1 for r in all_r if r.get("unstable")),
                        "invalid_count": sum(1 for r in all_r if not r.get("valid") and not r.get("unstable")),
                        "cf_bypass_count": sum(1 for r in all_r if r.get("cf_bypass")),
                    })

            elif self.path == "/api/auto/get":
                token = sanitize_token(body.get("token", "default"))
                self._json(200, get_auto_status(token, body.get("since", 0), body.get("session_id", "")))

            elif self.path == "/api/auto/save":
                token = sanitize_token(body.get("token", "default"))
                record = save_auto_config(token, body.get("config", {}))
                response = get_auto_status(token)
                response["saved"] = True
                response["config"] = record["config"]
                response["state"] = record["state"]
                self._json(200, response)

            elif self.path == "/api/auto/run-now":
                token = sanitize_token(body.get("token", "default"))
                started, message = start_auto_run(token, "manual")
                response = get_auto_status(token)
                response["started"] = started
                if not started:
                    response["error"] = message
                self._json(200, response)

            elif self.path == "/api/auto/stop":
                token = sanitize_token(body.get("token", "default"))
                stopped = stop_auto_run(token)
                response = get_auto_status(token, body.get("since", 0), body.get("session_id", ""))
                response["stopped"] = stopped
                self._json(200, response)

            elif self.path == "/api/auto/status":
                token = sanitize_token(body.get("token", "default"))
                self._json(200, get_auto_status(token, body.get("since", 0), body.get("session_id", "")))

            elif self.path == "/api/stop":
                sid = body.get("session_id", "")
                with sessions_lock:
                    s = sessions.get(sid)
                    if s and s.get("stop"):
                        s["stop"].set()
                self._json(200, {"ok": True})

            elif self.path == "/api/deep-check":
                # Optional deep check using nodriver
                proxy = body.get("proxy", "")
                if not proxy:
                    self._json(400, {"error": "proxy required"}); return
                if not NODRIVER_AVAILABLE:
                    self._json(200, {"success": False, "error": "nodriver not installed", "hint": "pip install nodriver"})
                    return
                target = body.get("target", TARGET_CHAT)
                result = run_deep_check(proxy, target)
                self._json(200, result)

            elif self.path == "/api/repo/save":
                # Accept full repo data (JSON array of objects) or legacy proxy list
                repo_data = body.get("repo", None)
                proxies = body.get("proxies", [])
                token = body.get("token", "default")
                if not token.replace("_","").isalnum():
                    token = "default"
                mode = body.get("mode", "merge")
                base_count = body.get("base_count", None)

                if repo_data is not None:
                    saved, response = save_repo_payload(token, repo_data, mode, base_count)
                    if saved is None:
                        log.warning("Repo save rejected", extra={"token": token, "response": response})
                        self._json(200, response)
                        return
                    response["url"] = f"/api/repo/{token}.json"
                    log.info("Repo saved (JSON)", extra={"token": token, "mode": response["mode"], "count": response["count"], "submitted_count": response["submitted_count"]})
                    self._json(200, response)
                else:
                    legacy_repo = [{"proxy": proxy} for proxy in proxies]
                    saved, response = save_repo_payload(token, legacy_repo, mode, base_count)
                    if saved is None:
                        log.warning("Repo save rejected", extra={"token": token, "response": response})
                        self._json(200, response)
                        return
                    response["url"] = f"/api/repo/{token}.txt"
                    log.info("Repo saved (txt)", extra={"token": token, "mode": response["mode"], "count": response["count"], "submitted_count": response["submitted_count"]})
                    self._json(200, response)

            elif self.path == "/api/fetch-proxies":
                # Fetch proxies from external sources
                if not FETCH_PROXIES_AVAILABLE:
                    self._json(200, {"error": "fetch_proxies 模块不可用"})
                    return
                source_id = body.get("source", "proxifly")
                limit = min(int(body.get("limit", 999999)), 999999)
                proxies, source_name, err = fetch_proxies(source_id, limit)
                if err:
                    self._json(200, {"error": err, "source": source_name})
                else:
                    self._json(200, {
                        "proxies": proxies,
                        "count": len(proxies),
                        "source": source_name,
                        "source_id": source_id,
                    })

            elif self.path == "/api/checked/save":
                proxies = body.get("proxies", [])
                token = sanitize_token(body.get("token", "default"))
                saved = write_checked_list(token, proxies)
                log.info(f"Checked proxies saved: token={token}, count={len(saved)}")
                self._json(200, {"ok": True, "count": len(saved)})

            elif self.path == "/api/checked/filter":
                # Given a list of proxies, return which ones are NOT yet checked
                proxies = body.get("proxies", [])
                token = sanitize_token(body.get("token", "default"))
                checked_set = {proxy_key(proxy) for proxy in read_checked_list(token)}
                unchecked = [p for p in proxies if proxy_key(p) not in checked_set]
                skipped = len(proxies) - len(unchecked)
                self._json(200, {
                    "unchecked": unchecked,
                    "skipped": skipped,
                    "total": len(proxies),
                    "checked_count": len(checked_set),
                })

            else:
                self.send_response(404); self.end_headers()

        except Exception as e:
            log.error(f"POST error: {e}")
            try:
                self._json(500, {"error": str(e)})
            except:
                pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Proxy-Auth")
        self.end_headers()

    def _json(self, code, data, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        for key, value in headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_static_file(self, file_name):
        fp = os.path.join(BASE_DIR, file_name)
        ext = os.path.splitext(fp)[1]
        ct = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".json": "application/json"}.get(ext, "application/octet-stream")
        if os.path.isfile(fp):
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            with open(fp, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    start_auto_scheduler()
    start_proxy_gateway()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info(f"Proxy Checker running at http://0.0.0.0:{PORT}")
    log.info(f"Deep check (nodriver): {'available' if NODRIVER_AVAILABLE else 'not installed'}")
    log.info(f"Concurrency: {MAX_CONCURRENT} | Rounds: {CHECK_ROUNDS}")
    log.info("Auto mode scheduler started")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
        server.server_close()
    except Exception as e:
        log.critical(f"Server crashed: {e}", exc_info=True)
