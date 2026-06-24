from proxy_checker.http.auth_routes import create_auth_blueprint
from proxy_checker.http.auto_routes import create_auto_blueprint
from proxy_checker.http.check_routes import create_check_blueprint
from proxy_checker.http.fetch_routes import create_fetch_blueprint
from proxy_checker.http.log_routes import create_log_blueprint
from proxy_checker.http.repo_routes import create_repo_blueprint
from proxy_checker.http.settings_routes import create_settings_blueprint
from proxy_checker.http.static_routes import create_static_blueprint


def register_app_blueprints(
    app,
    *,
    root_dir,
    auth_service,
    settings_provider,
    capabilities_provider,
    server_time_provider,
    save_settings,
    start_check,
    get_check_status,
    stop_check,
    deep_check,
    fetch_proxies,
    get_auto,
    save_auto,
    run_auto_now,
    stop_auto,
    status_auto,
    log_service,
    repo_service,
    read_repo_data,
    save_repo_payload,
    write_repo_data,
    read_checked_list,
    write_checked_list,
    include_repo=True,
):
    app.register_blueprint(create_static_blueprint(root_dir, auth_service))
    app.register_blueprint(create_auth_blueprint(auth_service))
    app.register_blueprint(create_settings_blueprint(
        auth_service,
        capabilities_provider=capabilities_provider,
        settings_provider=settings_provider,
        server_time_provider=server_time_provider,
        save_settings=save_settings,
    ))
    app.register_blueprint(create_check_blueprint(
        auth_service,
        start_check=start_check,
        get_status=get_check_status,
        stop_check=stop_check,
        deep_check=deep_check,
    ))
    app.register_blueprint(create_fetch_blueprint(auth_service, fetch_proxies=fetch_proxies))
    if include_repo:
        app.register_blueprint(create_repo_blueprint(
            auth_service,
            repo_service=repo_service,
            read_repo_data=read_repo_data,
            save_repo_payload=save_repo_payload,
            write_repo_data=write_repo_data,
            read_checked_list=read_checked_list,
            write_checked_list=write_checked_list,
        ))
    app.register_blueprint(create_log_blueprint(auth_service, log_service=log_service))
    app.register_blueprint(create_auto_blueprint(
        auth_service,
        get_auto=get_auto,
        save_auto=save_auto,
        run_auto_now=run_auto_now,
        stop_auto=stop_auto,
        status_auto=status_auto,
    ))
    return app
