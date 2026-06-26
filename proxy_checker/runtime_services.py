from dataclasses import dataclass

from proxy_checker.checking.engine import DEFAULT_TARGET_CHAT
from proxy_checker.config import LOG_FILE_PATH, Settings, ensure_runtime_dirs
from proxy_checker.gateway.runtime_gateway import create_runtime_gateway_services
from proxy_checker.migrate.v1_to_v2 import maybe_run_migration
from proxy_checker.http.runtime_http import create_runtime_http_service
from proxy_checker.services.auth_service import create_runtime_auth_service
from proxy_checker.services.deep_check_service import DeepCheckService
from proxy_checker.services.fetch_service import ProxyFetchService
from proxy_checker.services.log_service import LogService
from proxy_checker.services.logging_service import configure_logging
from proxy_checker.services.repo_update_service import RepoUpdateService
from proxy_checker.services.runtime_auto_service import create_runtime_auto_services
from proxy_checker.services.runtime_check_service import create_manual_check_service
from proxy_checker.services.runtime_lifecycle_service import RuntimeLifecycleService
from proxy_checker.services.runtime_options_service import create_runtime_options_service
from proxy_checker.services.runtime_settings_apply_service import RuntimeCheckEngineFactory, RuntimeSettingsApplyService
from proxy_checker.services.runtime_settings_payload_service import RuntimeSettingsPayloadService
from proxy_checker.services.runtime_settings_service import (
    create_runtime_capabilities_service,
    create_runtime_settings_service,
)
from proxy_checker.services.session_cleanup_service import SessionCleanupService
from proxy_checker.services.session_service import InMemorySessionStore
from proxy_checker.storage.tenant import create_tenant_storage_factory


class EngineRef:
    def __init__(self, engine):
        self.engine = engine

    def get(self):
        return self.engine


@dataclass(frozen=True)
class RuntimeServices:
    state: object
    log: object
    target_chat: str
    engine_ref: object
    auth_service: object
    check_engine_factory: object
    check_sessions: object
    proxy_gateway_service: object
    gateway_runtime_service: object
    deep_check_service: object
    proxy_fetch_service: object
    log_service: object
    repo_update_service: object
    settings_payload_service: object
    runtime_options_service: object
    runtime_settings_apply_service: object
    runtime_settings_service: object
    runtime_capabilities_service: object
    session_cleanup_service: object
    auto_runtime_store: object
    auto_record_service: object
    auto_coordinator_service: object
    auto_control_service: object
    manual_check_service: object
    lifecycle_service: object
    http_service: object

    @property
    def check_engine(self):
        return self.engine_ref.get()


def create_runtime_services():
    state = Settings.load()
    log = configure_logging(LOG_FILE_PATH)
    ensure_runtime_dirs()
    maybe_run_migration(logger=log)
    target_chat = DEFAULT_TARGET_CHAT
    storage_factory = create_tenant_storage_factory()
    auth_service = create_runtime_auth_service(state)
    check_engine_factory = RuntimeCheckEngineFactory(state)
    engine_ref = EngineRef(check_engine_factory.create())

    def apply_runtime_settings(settings):
        password_changed, new_engine = runtime_settings_apply_service.apply(settings)
        engine_ref.engine = new_engine
        return password_changed

    check_sessions = InMemorySessionStore()
    gateway_services = create_runtime_gateway_services(state=state, logger=log)
    proxy_gateway_service = gateway_services.gateway_service
    gateway_runtime_service = gateway_services.runtime_service
    deep_check_service = DeepCheckService(target_chat)
    proxy_fetch_service = ProxyFetchService()
    log_service = LogService()
    repo_update_service = RepoUpdateService()
    settings_payload_service = RuntimeSettingsPayloadService(
        state=state,
        proxy_gateway_service=proxy_gateway_service,
    )

    runtime_options_service = create_runtime_options_service(state)
    runtime_settings_apply_service = RuntimeSettingsApplyService(
        state=state,
        runtime_options_service=runtime_options_service,
        auth_service=auth_service,
        check_engine_factory=check_engine_factory,
    )
    runtime_settings_service = create_runtime_settings_service(
        state=state,
        auth_service=auth_service,
        settings_payload_service=settings_payload_service,
        apply_runtime_settings=apply_runtime_settings,
    )
    runtime_capabilities_service = create_runtime_capabilities_service(
        state=state,
        deep_check_service=deep_check_service,
        fetch_service=proxy_fetch_service,
        settings_provider=settings_payload_service.public_settings,
    )
    session_cleanup_service = SessionCleanupService(check_sessions, logger=log)
    auto_services = create_runtime_auto_services(
        state=state,
        runtime_options_service=runtime_options_service,
        fetch_service=proxy_fetch_service,
        check_engine_provider=engine_ref.get,
        repo_update_service=repo_update_service,
        logger=log,
        storage_factory=storage_factory,
    )
    manual_check_service = create_manual_check_service(
        state=state,
        session_store=check_sessions,
        auto_runtime_store=auto_services.runtime_store,
        check_engine_provider=engine_ref.get,
        runtime_options_service=runtime_options_service,
        logger=log,
        storage_factory=storage_factory,
    )
    lifecycle_service = RuntimeLifecycleService(
        state=state,
        session_cleanup_service=session_cleanup_service,
        auto_coordinator_service=auto_services.coordinator_service,
        gateway_runtime_service=gateway_runtime_service,
        deep_check_service=deep_check_service,
        logger=log,
    )
    http_service = create_runtime_http_service(
        state=state,
        auth_service=auth_service,
        runtime_options_service=runtime_options_service,
        runtime_capabilities_service=runtime_capabilities_service,
        runtime_settings_service=runtime_settings_service,
        log_service=log_service,
        manual_check_service=manual_check_service,
        auto_control_service=auto_services.control_service,
        deep_check_service=deep_check_service,
        proxy_fetch_service=proxy_fetch_service,
        logger=log,
    )

    return RuntimeServices(
        state=state,
        log=log,
        target_chat=target_chat,
        engine_ref=engine_ref,
        auth_service=auth_service,
        check_engine_factory=check_engine_factory,
        check_sessions=check_sessions,
        proxy_gateway_service=proxy_gateway_service,
        gateway_runtime_service=gateway_runtime_service,
        deep_check_service=deep_check_service,
        proxy_fetch_service=proxy_fetch_service,
        log_service=log_service,
        repo_update_service=repo_update_service,
        settings_payload_service=settings_payload_service,
        runtime_options_service=runtime_options_service,
        runtime_settings_apply_service=runtime_settings_apply_service,
        runtime_settings_service=runtime_settings_service,
        runtime_capabilities_service=runtime_capabilities_service,
        session_cleanup_service=session_cleanup_service,
        auto_runtime_store=auto_services.runtime_store,
        auto_record_service=auto_services.record_service,
        auto_coordinator_service=auto_services.coordinator_service,
        auto_control_service=auto_services.control_service,
        manual_check_service=manual_check_service,
        lifecycle_service=lifecycle_service,
        http_service=http_service,
    )
