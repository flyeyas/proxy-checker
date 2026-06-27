import threading
from socketserver import StreamRequestHandler, TCPServer, ThreadingMixIn

from proxy_forge.gateway.tunnel import (
    handle_connect_tunnel,
    handle_http_proxy_request,
    send_gateway_error,
)


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    daemon_threads = True
    allow_reuse_address = True


class ProxyGatewayHandler(StreamRequestHandler):
    timeout = 20
    gateway_service = None
    logger = None

    def handle(self):
        try:
            request_line = self.rfile.readline(65536)
            if not request_line:
                return
            headers = self._read_headers()
            parts = request_line.decode("iso-8859-1", errors="replace").strip().split()
            if len(parts) < 3:
                send_gateway_error(self.wfile, 400, "Bad Request")
                return
            method, target, version = parts[0].upper(), parts[1], parts[2]
            if method == "CONNECT":
                handle_connect_tunnel(
                    self.connection,
                    self.wfile,
                    self.gateway_service,
                    target,
                    timeout=self.timeout,
                    logger=self.logger,
                )
            else:
                handle_http_proxy_request(
                    self.connection,
                    self.rfile,
                    self.wfile,
                    self.gateway_service,
                    method,
                    target,
                    version,
                    headers,
                    timeout=self.timeout,
                    logger=self.logger,
                )
        except Exception as exc:
            self._log_warning("Proxy gateway request failed", {"error": str(exc)})

    def _log_warning(self, message, extra=None):
        if self.logger:
            self.logger.warning(message, extra=extra or {})

    def _read_headers(self):
        headers = []
        while True:
            line = self.rfile.readline(65536)
            if not line or line in (b"\r\n", b"\n"):
                break
            headers.append(line)
        return headers


def make_proxy_gateway_handler(gateway_service, timeout=20, logger=None):
    class ConfiguredProxyGatewayHandler(ProxyGatewayHandler):
        pass

    ConfiguredProxyGatewayHandler.timeout = timeout
    ConfiguredProxyGatewayHandler.gateway_service = gateway_service
    ConfiguredProxyGatewayHandler.logger = logger
    return ConfiguredProxyGatewayHandler


def start_proxy_gateway(bind, port, gateway_service, timeout=20, logger=None, enabled=True):
    if not enabled:
        if logger:
            logger.info("Proxy gateway disabled")
        return None
    if port <= 0:
        if logger:
            logger.info("Proxy gateway disabled by port")
        return None
    handler = make_proxy_gateway_handler(gateway_service, timeout=timeout, logger=logger)
    try:
        server = ThreadingTCPServer((bind, port), handler)
    except Exception as exc:
        if logger:
            logger.error("Proxy gateway failed to start", extra={"bind": bind, "port": port, "error": str(exc)})
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if logger:
        logger.info(
            f"Proxy gateway running at http://{bind}:{port} "
            f"with grades {','.join(sorted(gateway_service.allowed_grades()))}"
        )
    return server
