from proxy_forge.http.server_runner import serve_flask_http as run_flask_http


class RuntimeHttpService:
    def __init__(
        self,
        *,
        state,
        auth_service,
        runtime_options_service,
        runtime_capabilities_service,
        runtime_settings_service,
        log_service,
        manual_check_service,
        auto_control_service,
        deep_check_service,
        proxy_fetch_service,
        logger,
    ):
        self.state = state
        self.auth_service = auth_service
        self.runtime_options_service = runtime_options_service
        self.runtime_capabilities_service = runtime_capabilities_service
        self.runtime_settings_service = runtime_settings_service
        self.log_service = log_service
        self.manual_check_service = manual_check_service
        self.auto_control_service = auto_control_service
        self.deep_check_service = deep_check_service
        self.proxy_fetch_service = proxy_fetch_service
        self.log = logger

    def create_flask_app(self):
        from proxy_forge.app import create_app

        return create_app(
            root_dir=self.state.base_dir,
            auth_service=self.auth_service,
            settings_provider=self.runtime_settings_service.public_settings,
            capabilities_provider=self.runtime_capabilities_service.payload,
            server_time_provider=lambda: self.runtime_options_service.server_time_payload(self.state.app_timezone),
            save_settings=self.runtime_settings_service.save_payload,
            start_check=self.manual_check_service.start_payload,
            get_check_status=self.manual_check_service.status_payload,
            stop_check=self.manual_check_service.stop_payload,
            deep_check=self.deep_check_service.payload,
            fetch_proxies=self.proxy_fetch_service.payload,
            log_service=self.log_service,
            get_auto=self.auto_control_service.get_payload,
            save_auto=self.auto_control_service.save_payload,
            run_auto_now=self.auto_control_service.run_now_payload,
            stop_auto=self.auto_control_service.stop_payload,
            status_auto=self.auto_control_service.status_payload,
        )

    def serve_flask_http(self):
        return run_flask_http(
            self.create_flask_app,
            port=self.state.port,
            threads=self.state.http_threads,
            logger=self.log,
        )


def create_runtime_http_service(
    *,
    state,
    auth_service,
    runtime_options_service,
    runtime_capabilities_service,
    runtime_settings_service,
    log_service,
    manual_check_service,
    auto_control_service,
    deep_check_service,
    proxy_fetch_service,
    logger,
):
    return RuntimeHttpService(
        state=state,
        auth_service=auth_service,
        runtime_options_service=runtime_options_service,
        runtime_capabilities_service=runtime_capabilities_service,
        runtime_settings_service=runtime_settings_service,
        log_service=log_service,
        manual_check_service=manual_check_service,
        auto_control_service=auto_control_service,
        deep_check_service=deep_check_service,
        proxy_fetch_service=proxy_fetch_service,
        logger=logger,
    )
