from dataclasses import dataclass

from proxy_checker.config import (
    APP_TIMEZONE,
    AUTH_SESSION_DAYS,
    AUTH_SESSION_SECONDS,
    AUTH_SESSION_SECRET,
    AUTH_PASSWORD,
    BASE_DIR,
    CHECK_ROUNDS,
    DETECT_TIMEOUT,
    HTTP_THREADS,
    LOG_LIMIT,
    MAX_CHECK_ROUNDS,
    MAX_CONCURRENT,
    MAX_CONCURRENT_LIMIT,
    PORT,
    PROXY_GATEWAY_BIND,
    PROXY_GATEWAY_ENABLED,
    PROXY_GATEWAY_PORT,
    PROXY_GATEWAY_TIMEOUT,
    REPO_DIR,
    TIMEOUT,
)


@dataclass
class RuntimeState:
    base_dir: str
    repo_dir: str
    port: int
    http_threads: int
    timeout: int
    detect_timeout: int
    max_concurrent: int
    max_concurrent_limit: int
    check_rounds: int
    max_check_rounds: int
    log_limit: int
    app_timezone: str
    auth_password: str
    auth_session_days: int
    auth_session_seconds: int
    auth_session_secret: str
    proxy_gateway_enabled: bool
    proxy_gateway_bind: str
    proxy_gateway_port: int
    proxy_gateway_timeout: int

    @classmethod
    def from_config(cls):
        return cls(
            base_dir=BASE_DIR,
            repo_dir=REPO_DIR,
            port=PORT,
            http_threads=HTTP_THREADS,
            timeout=TIMEOUT,
            detect_timeout=DETECT_TIMEOUT,
            max_concurrent=MAX_CONCURRENT,
            max_concurrent_limit=MAX_CONCURRENT_LIMIT,
            check_rounds=CHECK_ROUNDS,
            max_check_rounds=MAX_CHECK_ROUNDS,
            log_limit=LOG_LIMIT,
            app_timezone=APP_TIMEZONE,
            auth_password=AUTH_PASSWORD,
            auth_session_days=AUTH_SESSION_DAYS,
            auth_session_seconds=AUTH_SESSION_SECONDS,
            auth_session_secret=AUTH_SESSION_SECRET,
            proxy_gateway_enabled=PROXY_GATEWAY_ENABLED,
            proxy_gateway_bind=PROXY_GATEWAY_BIND,
            proxy_gateway_port=PROXY_GATEWAY_PORT,
            proxy_gateway_timeout=PROXY_GATEWAY_TIMEOUT,
        )

    def settings_context(self):
        return {
            "timeout": self.timeout,
            "detect_timeout": self.detect_timeout,
            "max_concurrent": self.max_concurrent,
            "max_concurrent_limit": self.max_concurrent_limit,
            "check_rounds": self.check_rounds,
            "max_check_rounds": self.max_check_rounds,
            "log_limit": self.log_limit,
            "auth_password": self.auth_password,
            "auth_session_days": self.auth_session_days,
            "auth_session_seconds": self.auth_session_seconds,
            "auth_session_secret": self.auth_session_secret,
            "app_timezone": self.app_timezone,
        }

    def apply_resolved_settings(self, resolved):
        self.timeout = resolved["timeout"]
        self.detect_timeout = resolved["detect_timeout"]
        self.max_concurrent = resolved["max_concurrent"]
        self.max_concurrent_limit = resolved["max_concurrent_limit"]
        self.check_rounds = resolved["check_rounds"]
        self.max_check_rounds = resolved["max_check_rounds"]
        self.log_limit = resolved["log_limit"]
        self.auth_password = resolved["auth_password"]
        self.auth_session_days = resolved["auth_session_days"]
        self.auth_session_seconds = resolved["auth_session_seconds"]
        self.auth_session_secret = resolved["auth_session_secret"]
        self.app_timezone = resolved["app_timezone"]
