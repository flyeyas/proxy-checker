from dataclasses import dataclass

from proxy_checker.config import PROXY_GATEWAY_GRADES, PROXY_GATEWAY_TOKEN
from proxy_checker.gateway.server import start_proxy_gateway
from proxy_checker.services.proxy_gateway_service import ProxyGatewayService


@dataclass(frozen=True)
class RuntimeGatewayServices:
    gateway_service: ProxyGatewayService
    runtime_service: "RuntimeGatewayService"


class RuntimeGatewayService:
    def __init__(self, *, state, gateway_service, logger):
        self.state = state
        self.gateway_service = gateway_service
        self.log = logger

    def start(self):
        return start_proxy_gateway(
            self.state.proxy_gateway_bind,
            self.state.proxy_gateway_port,
            self.gateway_service,
            timeout=self.state.proxy_gateway_timeout,
            logger=self.log,
            enabled=self.state.proxy_gateway_enabled,
        )


def create_runtime_gateway_services(*, state, logger):
    gateway_service = ProxyGatewayService(state.repo_dir, PROXY_GATEWAY_TOKEN, PROXY_GATEWAY_GRADES)
    runtime_service = RuntimeGatewayService(
        state=state,
        gateway_service=gateway_service,
        logger=logger,
    )
    return RuntimeGatewayServices(
        gateway_service=gateway_service,
        runtime_service=runtime_service,
    )
