import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from proxy_forge.http.runtime_http import RuntimeHttpService, create_runtime_http_service


class RuntimeHttpServiceTest(unittest.TestCase):
    def setUp(self):
        self.state = SimpleNamespace(
            base_dir="/tmp/proxy-forge",
            repo_dir="/tmp/proxy-forge/repo_data",
            port=8888,
            http_threads=16,
            app_timezone="UTC",
        )
        self.service = RuntimeHttpService(
            state=self.state,
            auth_service=Mock(),
            runtime_options_service=Mock(),
            runtime_capabilities_service=Mock(),
            runtime_settings_service=Mock(public_settings=Mock(), save_payload=Mock()),
            log_service=Mock(),
            manual_check_service=Mock(),
            auto_control_service=Mock(),
            deep_check_service=Mock(),
            proxy_fetch_service=Mock(),
            logger=Mock(),
        )

    def test_serve_flask_http_delegates_to_runner(self):
        with patch("proxy_forge.http.runtime_http.run_flask_http") as serve:
            self.service.serve_flask_http()

        serve.assert_called_once()
        args, kwargs = serve.call_args
        self.assertEqual(args[0], self.service.create_flask_app)
        self.assertEqual(kwargs["port"], 8888)
        self.assertEqual(kwargs["threads"], 16)

    def test_create_runtime_http_service_wires_dependencies(self):
        deps = {
            "state": self.state,
            "auth_service": Mock(),
            "runtime_options_service": Mock(),
            "runtime_capabilities_service": Mock(),
            "runtime_settings_service": Mock(),
            "log_service": Mock(),
            "manual_check_service": Mock(),
            "auto_control_service": Mock(),
            "deep_check_service": Mock(),
            "proxy_fetch_service": Mock(),
            "logger": Mock(),
        }

        service = create_runtime_http_service(**deps)

        self.assertIsInstance(service, RuntimeHttpService)
        self.assertIs(service.state, deps["state"])
        self.assertIs(service.auth_service, deps["auth_service"])
        self.assertIs(service.runtime_options_service, deps["runtime_options_service"])
        self.assertIs(service.runtime_capabilities_service, deps["runtime_capabilities_service"])
        self.assertIs(service.runtime_settings_service, deps["runtime_settings_service"])
        self.assertIs(service.log_service, deps["log_service"])
        self.assertIs(service.manual_check_service, deps["manual_check_service"])
        self.assertIs(service.auto_control_service, deps["auto_control_service"])
        self.assertIs(service.deep_check_service, deps["deep_check_service"])
        self.assertIs(service.proxy_fetch_service, deps["proxy_fetch_service"])
        self.assertIs(service.log, deps["logger"])


if __name__ == "__main__":
    unittest.main()
