import time
from datetime import datetime, timedelta


def normalize_interval_hours(value):
    try:
        interval_hours = float(value)
    except (TypeError, ValueError):
        interval_hours = 6
    return max(0.01, min(720, interval_hours))


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


def default_auto_config(app_timezone, check_rounds, max_concurrent):
    return {
        "enabled": False,
        "schedule_type": "interval",
        "interval_hours": 6,
        "daily_time": "03:00",
        "timezone": app_timezone,
        "target_profile": "generic",
        "rounds": check_rounds,
        "max_concurrent": max_concurrent,
        "detect_mode": "skip",
        "repo_update_policy": "stable_only",
    }


def default_auto_state(config=None):
    config = config or {}
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


def normalize_auto_config(
    config,
    *,
    app_timezone,
    check_rounds,
    max_concurrent,
    repo_update_policies,
    normalize_target_profile,
    normalize_max_concurrent,
    normalize_timezone,
):
    config = config if isinstance(config, dict) else {}
    defaults = default_auto_config(app_timezone, check_rounds, max_concurrent)
    merged = {**defaults, **config}
    schedule_type = str(merged.get("schedule_type") or "interval")
    if schedule_type not in ("interval", "daily"):
        schedule_type = "interval"
    detect_mode = str(merged.get("detect_mode") or "skip")
    if detect_mode not in ("skip", "force"):
        detect_mode = "skip"
    repo_update_policy = str(merged.get("repo_update_policy") or "stable_only")
    if repo_update_policy not in repo_update_policies:
        repo_update_policy = "stable_only"
    return {
        "enabled": bool(merged.get("enabled")),
        "schedule_type": schedule_type,
        "interval_hours": normalize_interval_hours(merged.get("interval_hours", defaults["interval_hours"])),
        "daily_time": normalize_daily_time(merged.get("daily_time")),
        "timezone": normalize_timezone(merged.get("timezone", app_timezone)),
        "target_profile": normalize_target_profile(merged.get("target_profile")),
        "rounds": check_rounds,
        "max_concurrent": normalize_max_concurrent(max_concurrent),
        "detect_mode": detect_mode,
        "repo_update_policy": repo_update_policy,
    }


def compute_next_run(config, *, normalize_auto_config, get_timezone, now=None):
    config = normalize_auto_config(config)
    if not config.get("enabled"):
        return None
    now = time.time() if now is None else float(now)
    if config["schedule_type"] == "daily":
        hour, minute = [int(part) for part in config["daily_time"].split(":", 1)]
        current = datetime.fromtimestamp(now, get_timezone(config.get("timezone")))
        target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target.timestamp() <= now:
            target = target + timedelta(days=1)
        return int(target.timestamp())
    return int(now + config["interval_hours"] * 3600)
