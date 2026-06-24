import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from proxy_checker.config import PROXY_GATEWAY_GRADES, PROXY_GATEWAY_TOKEN
from proxy_checker.gateway.runtime_gateway import RuntimeGatewayService, create_runtime_gateway_services


class RuntimeGatewayServiceTest(unittest.TestCase):
    def test_start_delegates_to_gateway_server(self):
        state = SimpleNamespace(
            proxy_gateway_bind="127.0.0.1",
            proxy_gateway_port=7890,
            proxy_gateway_timeout=20,
            proxy_gateway_enabled=True,
        )
        gateway_service = Mock()
        logger = Mock()
        service = RuntimeGatewayService(state=state, gateway_service=gateway_service, logger=logger)

        with patch("proxy_checker.gateway.runtime_gateway.start_proxy_gateway") as start:
            service.start()

        start.assert_called_once_with(
            "127.0.0.1",
            7890,
            gateway_service,
            timeout=20,
            logger=logger,
            enabled=True,
        )

    def test_create_runtime_gateway_services_wires_gateway_defaults(self):
        state = SimpleNamespace(
            repo_dir="/tmp/repo",
            proxy_gateway_bind="127.0.0.1",
            proxy_gateway_port=7890,
            proxy_gateway_timeout=20,
            proxy_gateway_enabled=True,
        )
        logger = Mock()

        services = create_runtime_gateway_services(state=state, logger=logger)

        self.assertEqual(services.gateway_service.repo_dir, "/tmp/repo")
        self.assertEqual(services.gateway_service.token, PROXY_GATEWAY_TOKEN)
        self.assertEqual(services.gateway_service.grades, PROXY_GATEWAY_GRADES)
        self.assertIs(services.runtime_service.state, state)
        self.assertIs(services.runtime_service.gateway_service, services.gateway_service)
        self.assertIs(services.runtime_service.log, logger)


if __name__ == "__main__":
    unittest.main()
