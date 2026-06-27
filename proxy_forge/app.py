from flask import Flask

from proxy_forge.app_dependencies import DEFAULT_DEEP_CHECK, resolve_app_dependencies
from proxy_forge.http.blueprints import register_app_blueprints
from proxy_forge.http.cors import init_cors


def create_app(
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
    include_repo=True,
):
    dependencies = resolve_app_dependencies(
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
    app = Flask(__name__, static_folder=None)
    init_cors(app)

    return register_app_blueprints(
        app,
        include_repo=include_repo,
        **dependencies.blueprint_kwargs(),
    )
