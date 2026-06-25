from proxy_checker.runtime_services import create_runtime_services


services = create_runtime_services()


def public_settings_payload():
    return services.settings_payload_service.public_settings()


def runtime_config_payload():
    return services.settings_payload_service.runtime_config()


def start_proxy_gateway():
    return services.gateway_runtime_service.start()


def create_runtime_flask_app():
    return services.http_service.create_flask_app()


def serve_flask_http():
    return services.http_service.serve_flask_http()


def main():
    services.lifecycle_service.start_background_services()
    services.http_service.serve_flask_http()


if __name__ == "__main__":
    main()
