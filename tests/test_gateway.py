import base64
import io
import unittest
from unittest.mock import patch

from proxy_checker.gateway import tunnel
from proxy_checker.gateway.server import make_proxy_gateway_handler, start_proxy_gateway
from proxy_checker.gateway.upstream_pool import choose_upstream, parse_allowed_grades
from proxy_checker.services.proxy_gateway_service import ProxyGatewayService


class ProxyGatewayServiceTest(unittest.TestCase):
    def test_candidates_default_to_grade_ab(self):
        data = {
            "main": [
                {"proxy": "http://user:pass@example.com:8080", "grade": "A"},
                {"proxy": "https://secure.example.com", "grade": "B"},
                {"proxy": "http://skip.example.com:8080", "grade": "C"},
            ]
        }
        service = ProxyGatewayService("/tmp/no-scan", grades="A,B", read_repo=lambda token: data.get(token, []))
        service.repo_tokens = lambda: ["main"]

        candidates = service.candidates()

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["host"], "example.com")
        self.assertEqual(candidates[0]["port"], 8080)
        self.assertEqual(
            candidates[0]["auth"],
            "Proxy-Authorization: Basic " + base64.b64encode(b"user:pass").decode("ascii") + "\r\n",
        )
        self.assertEqual(candidates[1]["host"], "secure.example.com")
        self.assertEqual(candidates[1]["port"], 443)

    def test_ordered_candidates_rotates(self):
        data = {
            "main": [
                {"proxy": "http://one.example.com:8080", "grade": "A"},
                {"proxy": "http://two.example.com:8080", "grade": "B"},
            ]
        }
        service = ProxyGatewayService("/tmp/no-scan", grades="A,B", read_repo=lambda token: data.get(token, []))
        service.repo_tokens = lambda: ["main"]

        first = service.ordered_candidates()
        second = service.ordered_candidates()

        self.assertEqual(first[0]["host"], "one.example.com")
        self.assertEqual(second[0]["host"], "two.example.com")

    def test_gateway_handler_factory_injects_runtime_dependencies(self):
        service = ProxyGatewayService("/tmp/no-scan", grades="A")
        handler_class = make_proxy_gateway_handler(service, timeout=7, logger=None)

        self.assertIs(handler_class.gateway_service, service)
        self.assertEqual(handler_class.timeout, 7)

    def test_start_proxy_gateway_can_be_disabled_without_binding_port(self):
        service = ProxyGatewayService("/tmp/no-scan", grades="A")

        self.assertIsNone(start_proxy_gateway("127.0.0.1", 0, service, enabled=False))
        self.assertIsNone(start_proxy_gateway("127.0.0.1", 0, service, enabled=True))

    def test_missing_repo_dir_has_no_candidates(self):
        service = ProxyGatewayService("/tmp/no-scan", grades="A")

        self.assertEqual(service.repo_tokens(), [])
        self.assertEqual(service.candidates(), [])

    def test_parse_allowed_grades_defaults_to_ab(self):
        self.assertEqual(parse_allowed_grades("A; b, c"), {"A", "B", "C"})
        self.assertEqual(parse_allowed_grades(""), {"A", "B"})

    def test_choose_upstream_rotates_candidates(self):
        candidates = [{"host": "one"}, {"host": "two"}]

        ordered, next_index = choose_upstream(candidates, 1)

        self.assertEqual(ordered, [{"host": "two"}, {"host": "one"}])
        self.assertEqual(next_index, 0)

    def test_tunnel_rejects_http_request_without_host(self):
        writer = io.BytesIO()

        ok = tunnel.handle_http_proxy_request(
            object(),
            io.BytesIO(),
            writer,
            upstream_pool=ProxyGatewayService("/tmp/no-scan"),
            method="GET",
            target="/path",
            version="HTTP/1.1",
            headers=[],
        )

        self.assertFalse(ok)
        self.assertIn(b"400 Missing Host Header", writer.getvalue())

    def test_tunnel_returns_502_when_no_upstream_candidates(self):
        writer = io.BytesIO()

        ok = tunnel.handle_connect_tunnel(
            object(),
            writer,
            upstream_pool=ProxyGatewayService("/tmp/no-scan"),
            target="example.com:443",
        )

        self.assertFalse(ok)
        self.assertIn(b"502 No Available Upstream Proxy", writer.getvalue())

    def test_tunnel_builds_http_proxy_request_and_filters_proxy_headers(self):
        writer = io.BytesIO()
        client_connection = object()
        fake_socket = FakeSocket()
        upstream_pool = FakeUpstreamPool([
            {"scheme": "http", "host": "proxy.example.com", "port": 8080, "auth": "Proxy-Authorization: Basic upstream\r\n"}
        ])
        headers = [
            b"Host: example.com\r\n",
            b"Connection: keep-alive\r\n",
            b"Proxy-Authorization: Basic browser\r\n",
            b"Proxy-Connection: keep-alive\r\n",
            b"X-Test: yes\r\n",
            b"Content-Length: 5\r\n",
        ]

        with patch("proxy_checker.gateway.tunnel.open_upstream", return_value=fake_socket), \
                patch("proxy_checker.gateway.tunnel.relay") as relay_mock:
            ok = tunnel.handle_http_proxy_request(
                client_connection,
                io.BytesIO(b"hello"),
                writer,
                upstream_pool=upstream_pool,
                method="GET",
                target="/path",
                version="HTTP/1.1",
                headers=headers,
            )

        sent = bytes(fake_socket.sent)
        self.assertTrue(ok)
        self.assertIn(b"GET http://example.com/path HTTP/1.1\r\n", sent)
        self.assertIn(b"Host: example.com\r\n", sent)
        self.assertIn(b"X-Test: yes\r\n", sent)
        self.assertIn(b"Connection: close\r\n", sent)
        self.assertIn(b"Proxy-Authorization: Basic upstream\r\n", sent)
        self.assertNotIn(b"Proxy-Authorization: Basic browser\r\n", sent)
        self.assertNotIn(b"Proxy-Connection: keep-alive\r\n", sent)
        self.assertTrue(sent.endswith(b"\r\nhello"))
        relay_mock.assert_called_once_with(client_connection, fake_socket, 20)

    def test_tunnel_connect_success_writes_upstream_response_and_relays(self):
        writer = io.BytesIO()
        client_connection = object()
        upstream_socket = object()
        upstream_pool = FakeUpstreamPool([
            {"scheme": "http", "host": "proxy.example.com", "port": 8080, "auth": ""}
        ])
        response = b"HTTP/1.1 200 Connection Established\r\n\r\n"

        with patch("proxy_checker.gateway.tunnel.connect_via_upstream", return_value=(upstream_socket, response)), \
                patch("proxy_checker.gateway.tunnel.relay") as relay_mock:
            ok = tunnel.handle_connect_tunnel(
                client_connection,
                writer,
                upstream_pool=upstream_pool,
                target="example.com:443",
            )

        self.assertTrue(ok)
        self.assertEqual(writer.getvalue(), response)
        relay_mock.assert_called_once_with(client_connection, upstream_socket, 20)


class FakeSocket:
    def __init__(self):
        self.sent = bytearray()
        self.closed = False

    def sendall(self, data):
        self.sent.extend(data)

    def close(self):
        self.closed = True


class FakeUpstreamPool:
    def __init__(self, candidates):
        self._candidates = candidates

    def ordered_candidates(self):
        return list(self._candidates)


if __name__ == "__main__":
    unittest.main()
