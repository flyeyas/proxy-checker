import sys
import unittest
from unittest.mock import patch


class ServerRunnerTest(unittest.TestCase):
    def test_serve_flask_http_serves_via_waitress(self):
        app = object()
        logger = FakeLogger()
        served = {}

        def fake_serve(app_arg, *, host, port, threads):
            served["app"] = app_arg
            served["host"] = host
            served["port"] = port
            served["threads"] = threads

        fake_waitress = type(sys)("waitress")
        fake_waitress.serve = fake_serve

        from proxy_forge.http.server_runner import serve_flask_http

        with patch.dict(sys.modules, {"waitress": fake_waitress}):
            serve_flask_http(lambda: app, port=8888, threads=4, logger=logger)

        self.assertIs(served["app"], app)
        self.assertEqual(served["host"], "0.0.0.0")
        self.assertEqual(served["port"], 8888)
        self.assertEqual(served["threads"], 4)
        self.assertTrue(any("8888" in message for message in logger.messages))


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
