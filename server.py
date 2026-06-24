from proxy_checker.runtime import create_runtime


runtime = create_runtime()


def public_settings_payload():
    return runtime.public_settings_payload()


def runtime_config_payload():
    return runtime.runtime_config_payload()


def apply_runtime_settings(settings):
    return runtime.apply_runtime_settings(settings)


def start_proxy_gateway():
    return runtime.start_proxy_gateway()


def create_runtime_flask_app():
    return runtime.create_flask_app()


def build_legacy_handler():
    return runtime.build_legacy_handler()


def serve_legacy_http():
    return runtime.serve_legacy_http()


def serve_flask_http():
    return runtime.serve_flask_http()


def main():
    runtime.main()


if __name__ == "__main__":
    main()
