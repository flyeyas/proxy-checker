INTERRUPTED_ERROR = "服务重启，上一轮自动任务已中断"


def interrupt_auto_state(state, config, now, *, default_rounds, default_max_concurrent):
    if not state.get("running"):
        return None
    summary = {
        "status": "interrupted",
        "reason": "service_restart",
        "started_at": state.get("started_at"),
        "finished_at": now,
        "duration_seconds": 0,
        "target_profile": config.get("target_profile", "generic"),
        "rounds": config.get("rounds", default_rounds),
        "max_concurrent": config.get("max_concurrent", default_max_concurrent),
        "detect_mode": config.get("detect_mode", "skip"),
        "repo_update_policy": config.get("repo_update_policy", "stable_only"),
        "error": INTERRUPTED_ERROR,
    }
    state.update({
        "running": False,
        "status": "interrupted",
        "stage": "interrupted",
        "session_id": None,
        "finished_at": now,
        "next_run_at": now if config.get("enabled") else None,
        "error": INTERRUPTED_ERROR,
    })
    return summary


def resolve_schedule_state(config, state, is_running, now, compute_next_run):
    if not config.get("enabled") or is_running:
        return False, False
    next_run_at = state.get("next_run_at")
    if next_run_at is None:
        state["next_run_at"] = compute_next_run(config, now)
        return False, True
    try:
        due = float(next_run_at) <= now
    except (TypeError, ValueError):
        due = True
    return due, False
