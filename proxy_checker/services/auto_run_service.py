import time


def count_results(results):
    valid = sum(1 for result in results if result.get("valid"))
    unstable = sum(1 for result in results if result.get("unstable"))
    invalid = sum(1 for result in results if not result.get("valid") and not result.get("unstable"))
    return valid, unstable, invalid


def build_auto_summary(
    runtime,
    status,
    *,
    default_rounds,
    default_max_concurrent,
    default_timezone,
    error=None,
    repo_summary=None,
    now=None,
):
    results = runtime.get("results", [])
    valid, unstable, invalid = count_results(results)
    started_at = runtime.get("started_at") or time.time()
    finished_at = time.time() if now is None else now
    summary = {
        "status": status,
        "reason": runtime.get("reason", "schedule"),
        "started_at": int(started_at),
        "finished_at": int(finished_at),
        "duration_seconds": max(0, int(finished_at - started_at)),
        "target_profile": runtime.get("target_profile", "generic"),
        "rounds": runtime.get("rounds", default_rounds),
        "max_concurrent": runtime.get("max_concurrent", default_max_concurrent),
        "detect_mode": runtime.get("detect_mode", "skip"),
        "repo_update_policy": runtime.get("repo_update_policy", "stable_only"),
        "schedule_type": runtime.get("schedule_type"),
        "interval_hours": runtime.get("interval_hours"),
        "daily_time": runtime.get("daily_time"),
        "timezone": runtime.get("timezone", default_timezone),
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


def build_auto_log_entry(run_id, reason, started_at, config, target_name):
    return {
        "id": run_id,
        "type": "auto",
        "status": "running",
        "session_id": run_id,
        "reason": reason,
        "started_at": int(started_at),
        "target_profile": config["target_profile"],
        "target_name": target_name,
        "rounds": config["rounds"],
        "max_concurrent": config["max_concurrent"],
        "detect_mode": config["detect_mode"],
        "repo_update_policy": config["repo_update_policy"],
        "schedule_type": config["schedule_type"],
        "interval_hours": config["interval_hours"],
        "daily_time": config["daily_time"],
        "timezone": config["timezone"],
    }


def build_auto_runtime(run_id, log_id, reason, started_at, config, stop_event):
    return {
        "run_id": run_id,
        "log_id": log_id,
        "reason": reason,
        "stop": stop_event,
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


def build_failed_auto_runtime(run_id, reason, config, *, default_rounds, default_max_concurrent, started_at=None):
    return {
        "run_id": run_id,
        "reason": reason,
        "started_at": time.time() if started_at is None else started_at,
        "results": [],
        "done": 0,
        "total": 0,
        "target_profile": config.get("target_profile", "generic"),
        "rounds": config.get("rounds", default_rounds),
        "max_concurrent": config.get("max_concurrent", default_max_concurrent),
        "detect_mode": config.get("detect_mode", "skip"),
        "repo_update_policy": config.get("repo_update_policy", "stable_only"),
    }
