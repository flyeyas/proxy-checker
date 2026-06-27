import importlib.util

from proxy_forge.checking.engine import TARGET_PROFILE_OPTIONS
from proxy_forge.config import (
    APP_TIMEZONE,
    AUTH_COOKIE_NAME,
    AUTH_PASSWORD,
    AUTH_SESSION_SECRET,
    AUTH_SESSION_SECONDS,
    CHECK_ROUNDS,
    DETECT_TIMEOUT,
    LOG_LIMIT,
    MAX_CHECK_ROUNDS,
    MAX_CONCURRENT,
    MAX_CONCURRENT_LIMIT,
    PORT,
    PROXY_GATEWAY_BIND,
    PROXY_GATEWAY_ENABLED,
    PROXY_GATEWAY_GRADES,
    PROXY_GATEWAY_PORT,
    PROXY_GATEWAY_TOKEN,
    REPO_DIR,
    TIMEOUT,
    TIMEZONE_OPTIONS,
)
from proxy_forge.responses import error_response
from proxy_forge.services.auth_service import AuthService
from proxy_forge.services.deep_check_service import is_xvfb_available
from proxy_forge.services.fetch_service import ProxyFetchService
from proxy_forge.services.proxy_gateway_service import ProxyGatewayService
from proxy_forge.services.settings_service import build_public_settings
from proxy_forge.services.time_service import server_time_payload as build_server_time_payload


def create_default_auth_service():
    return AuthService(AUTH_PASSWORD, AUTH_SESSION_SECRET, AUTH_SESSION_SECONDS, AUTH_COOKIE_NAME)


def create_default_settings_provider():
    proxy_gateway = ProxyGatewayService(REPO_DIR, PROXY_GATEWAY_TOKEN, PROXY_GATEWAY_GRADES)

    def settings_provider():
        return build_public_settings(
            check_rounds=CHECK_ROUNDS,
            max_check_rounds=MAX_CHECK_ROUNDS,
            max_concurrent=MAX_CONCURRENT,
            max_concurrent_limit=MAX_CONCURRENT_LIMIT,
            timeout=TIMEOUT,
            detect_timeout=DETECT_TIMEOUT,
            auth_session_days=max(1, AUTH_SESSION_SECONDS // 86400),
            log_limit=LOG_LIMIT,
            timezone=APP_TIMEZONE,
            timezone_options=TIMEZONE_OPTIONS,
            password_configurable=False,
            port=PORT,
            proxy_gateway={
                "enabled": PROXY_GATEWAY_ENABLED,
                "bind": PROXY_GATEWAY_BIND,
                "port": PROXY_GATEWAY_PORT,
                "grades": sorted(proxy_gateway.allowed_grades()),
                "token": proxy_gateway.token or None,
            },
        )

    return settings_provider


def create_default_capabilities_provider(settings_provider):
    proxy_fetch = ProxyFetchService()

    def capabilities_provider():
        nodriver_available = importlib.util.find_spec("nodriver") is not None
        return {
            "nodriver": nodriver_available,
            "xvfb": is_xvfb_available(),
            "deep_check": nodriver_available,
            "fetch_proxies": proxy_fetch.available,
            "target_profiles": list(TARGET_PROFILE_OPTIONS),
            "max_concurrent": MAX_CONCURRENT,
            "max_concurrent_limit": MAX_CONCURRENT_LIMIT,
            "auto_mode": True,
            "auto_mode_hint": "后台自动任务仅在自托管 Python 服务中可用",
            "settings": settings_provider(),
            "proxy_sources": proxy_fetch.sources(),
            "hosted": "flask",
        }

    return capabilities_provider


def create_default_server_time_provider():
    return lambda: build_server_time_payload(APP_TIMEZONE, {item["id"] for item in TIMEZONE_OPTIONS}, APP_TIMEZONE)


def create_default_check_handlers():
    def unsupported(_data):
        return error_response("当前 Flask 检测路由尚未接入运行时检测逻辑")

    return unsupported, unsupported, unsupported


def create_default_deep_check_handler():
    def unsupported(_data):
        return error_response("nodriver not installed", success=False, hint="pip install nodriver")

    return unsupported


def create_default_fetch_proxies_handler():
    proxy_fetch = ProxyFetchService()

    def fetch_handler(data):
        return proxy_fetch.payload(data)

    return fetch_handler


def create_default_auto_handlers():
    def unsupported(_data):
        return error_response("当前 Flask 自动任务路由尚未接入运行时自动任务逻辑")

    return unsupported, unsupported, unsupported, unsupported, unsupported
