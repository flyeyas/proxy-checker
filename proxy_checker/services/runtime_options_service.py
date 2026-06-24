from proxy_checker.checking.engine import TARGET_PROFILE_OPTIONS
from proxy_checker.config import REPO_UPDATE_POLICIES, TIMEZONE_IDS
from proxy_checker.services.auto_config_service import (
    compute_next_run,
    default_auto_config,
    default_auto_state,
    normalize_auto_config,
)
from proxy_checker.services.check_options_service import (
    get_target_profile_name,
    normalize_max_concurrent,
    normalize_rounds,
    normalize_target_profile,
)
from proxy_checker.services.time_service import (
    format_timestamp,
    get_timezone,
    normalize_timezone,
    server_time_payload,
)


class RuntimeOptionsService:
    def __init__(
        self,
        *,
        app_timezone,
        check_rounds,
        max_check_rounds,
        max_concurrent,
        max_concurrent_limit,
        repo_update_policies,
        target_profiles,
        timezone_ids,
    ):
        self.app_timezone = app_timezone
        self.check_rounds = check_rounds
        self.max_check_rounds = max_check_rounds
        self.max_concurrent = max_concurrent
        self.max_concurrent_limit = max_concurrent_limit
        self.repo_update_policies = repo_update_policies
        self.target_profiles = target_profiles
        self.timezone_ids = timezone_ids

    def normalize_target_profile(self, value):
        return normalize_target_profile(value, self._setting(self.target_profiles))

    def get_target_profile_name(self, value):
        return get_target_profile_name(value, self._setting(self.target_profiles))

    def normalize_max_concurrent(self, value):
        return normalize_max_concurrent(
            value,
            self._setting(self.max_concurrent),
            self._setting(self.max_concurrent_limit),
        )

    def normalize_rounds(self, value):
        return normalize_rounds(
            value,
            self._setting(self.check_rounds),
            self._setting(self.max_check_rounds),
        )

    def normalize_timezone(self, value):
        return normalize_timezone(value, self._setting(self.timezone_ids), self._setting(self.app_timezone))

    def get_timezone(self, timezone_id):
        return get_timezone(timezone_id, self._setting(self.timezone_ids), self._setting(self.app_timezone))

    def format_timestamp(self, timestamp, timezone_id=None):
        return format_timestamp(
            timestamp,
            timezone_id or self._setting(self.app_timezone),
            self._setting(self.timezone_ids),
            self._setting(self.app_timezone),
        )

    def server_time_payload(self, timezone_id=None):
        return server_time_payload(
            timezone_id or self._setting(self.app_timezone),
            self._setting(self.timezone_ids),
            self._setting(self.app_timezone),
        )

    def default_auto_config(self):
        return default_auto_config(
            self._setting(self.app_timezone),
            self._setting(self.check_rounds),
            self._setting(self.max_concurrent),
        )

    def default_auto_state(self, config=None):
        return default_auto_state(config or self.default_auto_config())

    def normalize_auto_config(self, config):
        return normalize_auto_config(
            config,
            app_timezone=self._setting(self.app_timezone),
            check_rounds=self._setting(self.check_rounds),
            max_concurrent=self._setting(self.max_concurrent),
            repo_update_policies=self._setting(self.repo_update_policies),
            normalize_target_profile=self.normalize_target_profile,
            normalize_max_concurrent=self.normalize_max_concurrent,
            normalize_timezone=self.normalize_timezone,
        )

    def compute_next_run(self, config, now=None):
        return compute_next_run(
            config,
            normalize_auto_config=self.normalize_auto_config,
            get_timezone=self.get_timezone,
            now=now,
        )

    @staticmethod
    def _setting(value):
        return value() if callable(value) else value


def create_runtime_options_service(state):
    return RuntimeOptionsService(
        app_timezone=lambda: state.app_timezone,
        check_rounds=lambda: state.check_rounds,
        max_check_rounds=lambda: state.max_check_rounds,
        max_concurrent=lambda: state.max_concurrent,
        max_concurrent_limit=lambda: state.max_concurrent_limit,
        repo_update_policies=lambda: REPO_UPDATE_POLICIES,
        target_profiles=lambda: TARGET_PROFILE_OPTIONS,
        timezone_ids=lambda: TIMEZONE_IDS,
    )
