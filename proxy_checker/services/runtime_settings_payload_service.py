import os

from proxy_checker.config import TIMEZONE_OPTIONS
from proxy_checker.services.settings_service import build_public_settings, build_runtime_config


class RuntimeSettingsPayloadService:
    def __init__(self, *, state, proxy_gateway_service, timezone_options=TIMEZONE_OPTIONS):
        self.state = state
        self.proxy_gateway_service = proxy_gateway_service
        self.timezone_options = timezone_options

    def public_settings(self):
        return build_public_settings(
            check_rounds=self.state.check_rounds,
            max_check_rounds=self.state.max_check_rounds,
            max_concurrent=self.state.max_concurrent,
            max_concurrent_limit=self.state.max_concurrent_limit,
            timeout=self.state.timeout,
            detect_timeout=self.state.detect_timeout,
            auth_session_days=self.state.auth_session_days,
            log_limit=self.state.log_limit,
            timezone=self.state.app_timezone,
            timezone_options=self.timezone_options,
            password_configurable="AUTH_PASSWORD" not in os.environ,
            port=self.state.port,
            proxy_gateway={
                "enabled": self.state.proxy_gateway_enabled,
                "bind": self.state.proxy_gateway_bind,
                "port": self.state.proxy_gateway_port,
                "grades": sorted(self.proxy_gateway_service.allowed_grades()),
                "token": self.proxy_gateway_service.token or None,
            },
        )

    def runtime_config(self):
        return build_runtime_config(
            check_rounds=self.state.check_rounds,
            max_check_rounds=self.state.max_check_rounds,
            max_concurrent=self.state.max_concurrent,
            max_concurrent_limit=self.state.max_concurrent_limit,
            timeout=self.state.timeout,
            detect_timeout=self.state.detect_timeout,
            auth_session_days=self.state.auth_session_days,
            log_limit=self.state.log_limit,
            timezone=self.state.app_timezone,
        )
