from proxy_checker.runtime_services import create_runtime_services


class ProxyCheckerRuntime:
    def __init__(self):
        services = create_runtime_services(
            apply_runtime_settings=self.apply_runtime_settings,
            check_engine_provider=lambda: self.check_engine,
        )
        self.state = services.state
        self.log = services.log
        self.target_chat = services.target_chat
        self.auth_service = services.auth_service
        self.check_engine_factory = services.check_engine_factory
        self.check_engine = services.check_engine
        self.check_sessions = services.check_sessions
        self.proxy_gateway_service = services.proxy_gateway_service
        self.gateway_runtime_service = services.gateway_runtime_service
        self.deep_check_service = services.deep_check_service
        self.proxy_fetch_service = services.proxy_fetch_service
        self.log_service = services.log_service
        self.repo_update_service = services.repo_update_service
        self.settings_payload_service = services.settings_payload_service
        self.runtime_options_service = services.runtime_options_service
        self.runtime_settings_apply_service = services.runtime_settings_apply_service
        self.runtime_settings_service = services.runtime_settings_service
        self.runtime_capabilities_service = services.runtime_capabilities_service
        self.session_cleanup_service = services.session_cleanup_service
        self.auto_runtime_store = services.auto_runtime_store
        self.auto_record_service = services.auto_record_service
        self.auto_coordinator_service = services.auto_coordinator_service
        self.auto_control_service = services.auto_control_service
        self.manual_check_service = services.manual_check_service
        self.lifecycle_service = services.lifecycle_service
        self.http_service = services.http_service

    def create_check_engine(self):
        return self.check_engine_factory.create()

    def public_settings_payload(self):
        return self.settings_payload_service.public_settings()

    def runtime_config_payload(self):
        return self.settings_payload_service.runtime_config()

    def apply_runtime_settings(self, settings):
        password_changed, self.check_engine = self.runtime_settings_apply_service.apply(settings)
        return password_changed

    def start_proxy_gateway(self):
        return self.gateway_runtime_service.start()

    def create_flask_app(self):
        return self.http_service.create_flask_app()

    def build_legacy_handler(self):
        return self.http_service.build_legacy_handler()

    def serve_legacy_http(self):
        return self.http_service.serve_legacy_http()

    def serve_flask_http(self):
        return self.http_service.serve_flask_http()

    def start_background_services(self):
        return self.lifecycle_service.start_background_services()

    def main(self):
        self.start_background_services()
        self.serve_flask_http()


def create_runtime():
    return ProxyCheckerRuntime()
