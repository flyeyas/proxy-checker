from dataclasses import dataclass

from proxy_forge.app_defaults import (
    create_default_auth_service,
    create_default_auto_handlers,
    create_default_capabilities_provider,
    create_default_check_handlers,
    create_default_deep_check_handler,
    create_default_fetch_proxies_handler,
    create_default_server_time_provider,
    create_default_settings_provider,
)
from proxy_forge.config import BASE_DIR
from proxy_forge.services.log_service import LogService


DEFAULT_DEEP_CHECK = object()


@dataclass(frozen=True)
class AppDependencies:
    root_dir: str
    auth_service: object
    settings_provider: object
    capabilities_provider: object
    server_time_provider: object
    save_settings: object
    start_check: object
    get_check_status: object
    stop_check: object
    deep_check: object
    fetch_proxies: object
    get_auto: object
    save_auto: object
    run_auto_now: object
    stop_auto: object
    status_auto: object
    log_service: object
    repo_service: object

    def blueprint_kwargs(self):
        return self.__dict__.copy()


def resolve_app_dependencies(
    *,
    root_dir=None,
    auth_service=None,
    settings_provider=None,
    capabilities_provider=None,
    server_time_provider=None,
    save_settings=None,
    start_check=None,
    get_check_status=None,
    stop_check=None,
    deep_check=DEFAULT_DEEP_CHECK,
    fetch_proxies=None,
    get_auto=None,
    save_auto=None,
    run_auto_now=None,
    stop_auto=None,
    status_auto=None,
    log_service=None,
    repo_service=None,
):
    root_dir = root_dir or BASE_DIR
    auth_service = auth_service or create_default_auth_service()
    settings_provider = settings_provider or create_default_settings_provider()
    capabilities_provider = capabilities_provider or create_default_capabilities_provider(settings_provider)
    server_time_provider = server_time_provider or create_default_server_time_provider()
    log_service = log_service or LogService()
    if deep_check is DEFAULT_DEEP_CHECK:
        deep_check = create_default_deep_check_handler()
    fetch_proxies = fetch_proxies or create_default_fetch_proxies_handler()
    if start_check is None or get_check_status is None or stop_check is None:
        default_start, default_status, default_stop = create_default_check_handlers()
        start_check = start_check or default_start
        get_check_status = get_check_status or default_status
        stop_check = stop_check or default_stop
    if get_auto is None or save_auto is None or run_auto_now is None or stop_auto is None or status_auto is None:
        default_get, default_save, default_run, default_stop_auto, default_status_auto = create_default_auto_handlers()
        get_auto = get_auto or default_get
        save_auto = save_auto or default_save
        run_auto_now = run_auto_now or default_run
        stop_auto = stop_auto or default_stop_auto
        status_auto = status_auto or default_status_auto
    return AppDependencies(
        root_dir=root_dir,
        auth_service=auth_service,
        settings_provider=settings_provider,
        capabilities_provider=capabilities_provider,
        server_time_provider=server_time_provider,
        save_settings=save_settings,
        start_check=start_check,
        get_check_status=get_check_status,
        stop_check=stop_check,
        deep_check=deep_check,
        fetch_proxies=fetch_proxies,
        get_auto=get_auto,
        save_auto=save_auto,
        run_auto_now=run_auto_now,
        stop_auto=stop_auto,
        status_auto=status_auto,
        log_service=log_service,
        repo_service=repo_service,
    )
