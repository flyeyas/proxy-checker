def get_int_from(data, key, default):
    try:
        return int(data.get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default


def build_public_settings(
    *,
    check_rounds,
    max_check_rounds,
    max_concurrent,
    max_concurrent_limit,
    timeout,
    detect_timeout,
    auth_session_days,
    log_limit,
    timezone,
    timezone_options,
    password_configurable,
    port=None,
    proxy_gateway=None,
):
    payload = {
        "check_rounds": check_rounds,
        "max_check_rounds": max_check_rounds,
        "max_concurrent": max_concurrent,
        "max_concurrent_limit": max_concurrent_limit,
        "timeout": timeout,
        "detect_timeout": detect_timeout,
        "auth_session_days": auth_session_days,
        "log_limit": log_limit,
        "timezone": timezone,
        "timezone_options": list(timezone_options),
        "password_configurable": password_configurable,
    }
    if port is not None:
        payload["port"] = port
    if proxy_gateway is not None:
        payload["proxy_gateway"] = proxy_gateway
    return payload


def build_runtime_config(
    *,
    check_rounds,
    max_check_rounds,
    max_concurrent,
    max_concurrent_limit,
    timeout,
    detect_timeout,
    auth_session_days,
    log_limit,
    timezone,
):
    return {
        "check_rounds": check_rounds,
        "max_check_rounds": max_check_rounds,
        "max_concurrent": max_concurrent,
        "max_concurrent_limit": max_concurrent_limit,
        "timeout": timeout,
        "detect_timeout": detect_timeout,
        "auth_session_days": auth_session_days,
        "log_limit": log_limit,
        "timezone": timezone,
    }
