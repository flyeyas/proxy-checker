import builtins
import unittest
from unittest.mock import patch

from proxy_checker.http.server_runner import serve_flask_http, serve_legacy_http


class ServerRunnerTest(unittest.TestCase):
    def test_serve_legacy_http_builds_server_and_runs_forever(self):
        logger = FakeLogger()
        server_class = FakeServerClass()

        serve_legacy_http(8888, lambda: "handler", logger, server_class)

        self.assertEqual(server_class.address, ("0.0.0.0", 8888))
        self.assertEqual(server_class.handler, "handler")
        self.assertTrue(server_class.server.served)
        self.assertIn("legacy HTTP server", logger.messages[0])

    def test_serve_flask_http_falls_back_when_waitress_missing(self):
        called = []

        def fake_import(name, *args, **kwargs):
            if name == "waitress":
                raise ImportError("missing")
            return original_import(name, *args, **kwargs)

        original_import = builtins.__import__
        with patch("builtins.__import__", side_effect=fake_import):
            serve_flask_http(
                lambda: object(),
                port=8888,
                threads=4,
                logger=FakeLogger(),
                legacy_server=lambda: called.append(True),
            )

        self.assertEqual(called, [True])


class FakeServerClass:
    def __call__(self, address, handler, logger=None):
        self.address = address
        self.handler = handler
        self.logger = logger
        self.server = FakeServer()
        return self.server


class FakeServer:
    def __init__(self):
        self.served = False

    def serve_forever(self):
        self.served = True

    def server_close(self):
        pass


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)

    def warning(self, message):
        self.messages.append(message)

    def critical(self, message, **_kwargs):
        self.messages.append(message)


if __name__ == "__main__":
    unittest.main()
