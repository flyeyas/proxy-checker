from proxy_forge.checking.engine import TARGET_PROFILE_OPTIONS
from proxy_forge.services.settings_service import get_int_from
from proxy_forge.storage.config_store import read_local_config, write_local_config


def normalize_timeout(value, default):
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = default
    return max(3, min(120, timeout))


def resolve_runtime_settings(settings, current, *, normalize_timezone, password_env=False, secret_env=False):
    settings = settings if isinstance(settings, dict) else {}
    updated = dict(current)
    updated["max_check_rounds"] = max(1, min(10, get_int_from(settings, "max_check_rounds", current["max_check_rounds"])))
    updated["check_rounds"] = max(1, min(updated["max_check_rounds"], get_int_from(settings, "check_rounds", current["check_rounds"])))
    updated["max_concurrent_limit"] = max(1, min(1000, get_int_from(settings, "max_concurrent_limit", current["max_concurrent_limit"])))
    updated["max_concurrent"] = max(1, min(updated["max_concurrent_limit"], get_int_from(settings, "max_concurrent", current["max_concurrent"])))
    updated["timeout"] = normalize_timeout(settings.get("timeout"), current["timeout"])
    updated["detect_timeout"] = normalize_timeout(settings.get("detect_timeout"), current["detect_timeout"])
    updated["auth_session_days"] = max(1, min(365, get_int_from(settings, "auth_session_days", current["auth_session_days"])))
    updated["auth_session_seconds"] = updated["auth_session_days"] * 86400
    updated["log_limit"] = max(20, min(1000, get_int_from(settings, "log_limit", current["log_limit"])))
    updated["app_timezone"] = normalize_timezone(settings.get("timezone", current["app_timezone"]))

    new_password = str(settings.get("auth_password") or "").strip()
    password_changed = False
    if new_password and not password_env and new_password != current["auth_password"]:
        updated["auth_password"] = new_password
        if not secret_env:
            updated["auth_session_secret"] = new_password
        password_changed = True
    return updated, password_changed


class RuntimeSettingsService:
    def __init__(
        self,
        *,
        apply_runtime_settings,
        read_local_config,
        write_local_config,
        runtime_config,
        public_settings,
        auth_password,
        make_auth_token,
        session_seconds,
    ):
        self.apply_runtime_settings = apply_runtime_settings
        self.read_local_config = read_local_config
        self.write_local_config = write_local_config
        self.runtime_config = runtime_config
        self.public_settings = public_settings
        self.auth_password = auth_password
        self.make_auth_token = make_auth_token
        self.session_seconds = session_seconds

    def save_runtime_settings(self, settings):
        local_config = self.read_local_config()
        if not isinstance(local_config, dict):
            local_config = {}
        password_changed = self.apply_runtime_settings(settings)
        local_config.update(self.runtime_config())
        if password_changed:
            local_config["auth_password"] = self._setting(self.auth_password)
        self.write_local_config(local_config)
        return password_changed

    def save_payload(self, settings):
        password_changed = self.save_runtime_settings(settings)
        response = {
            "ok": True,
            "settings": self.public_settings(),
            "password_changed": password_changed,
        }
        if password_changed:
            response["token"] = self.make_auth_token()
            response["expires_in"] = self._setting(self.session_seconds)
        return response

    @staticmethod
    def _setting(value):
        return value() if callable(value) else value


def create_runtime_settings_service(
    *,
    state,
    auth_service,
    settings_payload_service,
    apply_runtime_settings,
):
    return RuntimeSettingsService(
        apply_runtime_settings=apply_runtime_settings,
        read_local_config=read_local_config,
        write_local_config=write_local_config,
        runtime_config=settings_payload_service.runtime_config,
        public_settings=settings_payload_service.public_settings,
        auth_password=lambda: state.auth_password,
        make_auth_token=auth_service.make_token,
        session_seconds=lambda: state.auth_session_seconds,
    )


class RuntimeCapabilitiesService:
    def __init__(
        self,
        *,
        deep_check_service,
        fetch_service,
        target_profiles,
        max_concurrent,
        max_concurrent_limit,
        settings_provider,
    ):
        self.deep_check_service = deep_check_service
        self.fetch_service = fetch_service
        self.target_profiles = target_profiles
        self.max_concurrent = max_concurrent
        self.max_concurrent_limit = max_concurrent_limit
        self.settings_provider = settings_provider

    def payload(self):
        return {
            "nodriver": self.deep_check_service.available,
            "xvfb": self.deep_check_service.xvfb_available,
            "deep_check": self.deep_check_service.available,
            "fetch_proxies": self.fetch_service.available,
            "target_profiles": list(self._setting(self.target_profiles)),
            "max_concurrent": self._setting(self.max_concurrent),
            "max_concurrent_limit": self._setting(self.max_concurrent_limit),
            "auto_mode": True,
            "auto_mode_hint": "后台自动任务仅在自托管 Python 服务中可用",
            "settings": self.settings_provider(),
            "proxy_sources": self.fetch_service.sources(),
        }

    @staticmethod
    def _setting(value):
        return value() if callable(value) else value


def create_runtime_capabilities_service(
    *,
    state,
    deep_check_service,
    fetch_service,
    settings_provider,
    target_profiles=TARGET_PROFILE_OPTIONS,
):
    return RuntimeCapabilitiesService(
        deep_check_service=deep_check_service,
        fetch_service=fetch_service,
        target_profiles=lambda: target_profiles,
        max_concurrent=lambda: state.max_concurrent,
        max_concurrent_limit=lambda: state.max_concurrent_limit,
        settings_provider=settings_provider,
    )
