from proxy_forge.app import create_app
from proxy_forge.checking.engine import CheckConfig, ProxyCheckEngine, TARGET_PROFILE_OPTIONS
from proxy_forge.config import (
    APP_TIMEZONE,
    AUTH_COOKIE_NAME,
    AUTH_PASSWORD,
    AUTH_SESSION_DAYS,
    AUTH_SESSION_SECRET,
    AUTH_SESSION_SECONDS,
    BASE_DIR,
    CHECK_ROUNDS,
    DETECT_TIMEOUT,
    LOG_LIMIT,
    MAX_CHECK_ROUNDS,
    MAX_CONCURRENT,
    MAX_CONCURRENT_LIMIT,
    TIMEOUT,
    TIMEZONE_IDS,
    TIMEZONE_OPTIONS,
)
from proxy_forge.http.auth_utils import unauthorized_response
from proxy_forge.responses import error_response, ok_response
from proxy_forge.services.auth_service import AuthService
from proxy_forge.services.auto_run_service import count_results
from proxy_forge.services.check_options_service import (
    get_target_profile_name,
    normalize_max_concurrent as normalize_max_concurrent_value,
    normalize_rounds as normalize_rounds_value,
    normalize_target_profile as normalize_target_profile_value,
)
from proxy_forge.services.check_service import ManualCheckService
from proxy_forge.services.fetch_service import ProxyFetchService
from proxy_forge.services.session_cleanup_service import SessionCleanupService
from proxy_forge.services.session_service import InMemorySessionStore
from proxy_forge.services.settings_service import build_public_settings
from proxy_forge.services.time_service import server_time_payload as build_server_time_payload


ROOT_DIR = BASE_DIR
SERVERLESS_UNSUPPORTED_AUTO_MESSAGE = "Vercel / Serverless 不支持后台自动任务，请使用自托管 Python 服务"

auth_service = AuthService(AUTH_PASSWORD, AUTH_SESSION_SECRET, AUTH_SESSION_SECONDS, AUTH_COOKIE_NAME)
check_engine = ProxyCheckEngine(
    CheckConfig(
        timeout=TIMEOUT,
        detect_timeout=DETECT_TIMEOUT,
        check_rounds=CHECK_ROUNDS,
    )
)
check_sessions = InMemorySessionStore()


def normalize_target_profile(value):
    return normalize_target_profile_value(value, TARGET_PROFILE_OPTIONS)


def normalize_max_concurrent(value):
    return normalize_max_concurrent_value(value, MAX_CONCURRENT, MAX_CONCURRENT_LIMIT)


def normalize_rounds(value):
    return normalize_rounds_value(value, CHECK_ROUNDS, MAX_CHECK_ROUNDS)


def public_settings_payload():
    return build_public_settings(
        check_rounds=CHECK_ROUNDS,
        max_check_rounds=MAX_CHECK_ROUNDS,
        max_concurrent=MAX_CONCURRENT,
        max_concurrent_limit=MAX_CONCURRENT_LIMIT,
        timeout=TIMEOUT,
        detect_timeout=DETECT_TIMEOUT,
        auth_session_days=AUTH_SESSION_DAYS,
        log_limit=LOG_LIMIT,
        timezone=APP_TIMEZONE,
        timezone_options=TIMEZONE_OPTIONS,
        password_configurable=False,
    )


def server_time_payload():
    return build_server_time_payload(APP_TIMEZONE, TIMEZONE_IDS, APP_TIMEZONE)


def serverless_capabilities_payload():
    return {
        "nodriver": False,
        "xvfb": False,
        "deep_check": False,
        "fetch_proxies": proxy_fetch_service.available,
        "target_profiles": list(TARGET_PROFILE_OPTIONS),
        "max_concurrent": MAX_CONCURRENT,
        "max_concurrent_limit": MAX_CONCURRENT_LIMIT,
        "auto_mode": False,
        "auto_mode_hint": SERVERLESS_UNSUPPORTED_AUTO_MESSAGE,
        "proxy_sources": proxy_fetch_service.sources(),
        "hosted": "vercel",
    }


def save_settings_payload(_settings):
    return error_response(
        "Vercel / Serverless 不支持保存运行设置，请使用自托管 Python 服务",
        settings=public_settings_payload(),
    )


def serverless_target_name(value):
    return get_target_profile_name(value, TARGET_PROFILE_OPTIONS)


def start_log(_token, _entry):
    return ""


def finish_log(*_args):
    return None


def auto_unsupported_payload(_data):
    return error_response(
        SERVERLESS_UNSUPPORTED_AUTO_MESSAGE,
        auto_mode=False,
        server_time=server_time_payload(),
    )


class ServerlessLogService:
    def payload(self, _token):
        return {"logs": [], "count": 0, "server_time": server_time_payload()}

    def clear(self, _token):
        return ok_response(logs=[], count=0)


class ServerlessProxyFetchService(ProxyFetchService):
    def payload(self, data):
        source_id = data.get("source", "proxifly")
        try:
            limit = min(int(data.get("limit", 500)), 2000)
        except (TypeError, ValueError):
            limit = 500
        proxies, source_name, error = self.fetch(source_id, limit)
        if error:
            return error_response(error, source=source_name)
        return {
            "proxies": proxies,
            "count": len(proxies),
            "source": source_name,
            "source_id": source_id,
        }


manual_check_service = ManualCheckService(
    session_store=check_sessions,
    check_engine=check_engine,
    normalize_rounds=normalize_rounds,
    normalize_target_profile=normalize_target_profile,
    normalize_max_concurrent=normalize_max_concurrent,
    target_name=serverless_target_name,
    is_auto_running=lambda _token: False,
    start_log=start_log,
    finish_log=finish_log,
    count_results=count_results,
    app_timezone=APP_TIMEZONE,
    default_rounds=CHECK_ROUNDS,
    default_max_concurrent=MAX_CONCURRENT,
)
proxy_fetch_service = ServerlessProxyFetchService()
log_service = ServerlessLogService()
SessionCleanupService(check_sessions).start()


def create_serverless_app():
    return create_app(
        root_dir=ROOT_DIR,
        auth_service=auth_service,
        capabilities_provider=serverless_capabilities_payload,
        settings_provider=public_settings_payload,
        server_time_provider=server_time_payload,
        save_settings=save_settings_payload,
        start_check=manual_check_service.start_payload,
        get_check_status=manual_check_service.status_payload,
        stop_check=manual_check_service.stop_payload,
        deep_check=None,
        fetch_proxies=proxy_fetch_service.payload,
        log_service=log_service,
        get_auto=auto_unsupported_payload,
        save_auto=auto_unsupported_payload,
        run_auto_now=auto_unsupported_payload,
        stop_auto=auto_unsupported_payload,
        status_auto=auto_unsupported_payload,
        include_repo=False,
    )


app = create_serverless_app()

__all__ = [
    "AUTH_PASSWORD",
    "app",
    "create_serverless_app",
    "unauthorized_response",
]
