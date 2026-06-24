import unittest
from unittest.mock import Mock

from proxy_checker.runtime import ProxyCheckerRuntime


class ProxyCheckerRuntimeTest(unittest.TestCase):
    def test_serve_flask_http_delegates_to_http_service(self):
        runtime = ProxyCheckerRuntime()
        runtime.http_service = Mock()

        runtime.serve_flask_http()

        runtime.http_service.serve_flask_http.assert_called_once_with()

    def test_serve_legacy_http_delegates_to_http_service(self):
        runtime = ProxyCheckerRuntime()
        runtime.http_service = Mock()

        runtime.serve_legacy_http()

        runtime.http_service.serve_legacy_http.assert_called_once_with()

    def test_start_background_services_delegates_to_lifecycle_service(self):
        runtime = ProxyCheckerRuntime()
        runtime.lifecycle_service = Mock()

        runtime.start_background_services()

        runtime.lifecycle_service.start_background_services.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
