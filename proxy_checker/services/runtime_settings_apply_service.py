import os

from proxy_checker.checking.engine import CheckConfig, ProxyCheckEngine
from proxy_checker.services.runtime_settings_service import resolve_runtime_settings
from proxy_checker.storage.log_store import set_log_limit


class RuntimeCheckEngineFactory:
    def __init__(self, state):
        self.state = state

    def create(self):
        return ProxyCheckEngine(
            CheckConfig(
                timeout=self.state.timeout,
                detect_timeout=self.state.detect_timeout,
                check_rounds=self.state.check_rounds,
            )
        )


class RuntimeSettingsApplyService:
    def __init__(
        self,
        *,
        state,
        runtime_options_service,
        auth_service,
        check_engine_factory,
        environ=os.environ,
        set_log_limit_func=set_log_limit,
    ):
        self.state = state
        self.runtime_options_service = runtime_options_service
        self.auth_service = auth_service
        self.check_engine_factory = check_engine_factory
        self.environ = environ
        self.set_log_limit = set_log_limit_func

    def apply(self, settings):
        resolved, password_changed = resolve_runtime_settings(
            settings,
            self.state.settings_context(),
            normalize_timezone=self.runtime_options_service.normalize_timezone,
            password_env="AUTH_PASSWORD" in self.environ,
            secret_env="AUTH_SESSION_SECRET" in self.environ,
        )
        self.state.apply_resolved_settings(resolved)
        self.set_log_limit(self.state.log_limit)
        self.auth_service.configure(
            self.state.auth_password,
            self.state.auth_session_secret,
            self.state.auth_session_seconds,
        )
        return password_changed, self.check_engine_factory.create()
