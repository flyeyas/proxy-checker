import unittest
from pathlib import Path

from proxy_checker.config import HTTP_THREADS


class EntrypointConfigTest(unittest.TestCase):
    def test_http_threads_is_bounded(self):
        self.assertGreaterEqual(HTTP_THREADS, 1)
        self.assertLessEqual(HTTP_THREADS, 128)

    def test_waitress_dependency_and_entrypoint_are_declared(self):
        root = Path(__file__).resolve().parents[1]
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")
        server = (root / "server.py").read_text(encoding="utf-8")
        runtime_http = (root / "proxy_checker" / "http" / "runtime_http.py").read_text(encoding="utf-8")
        runner = (root / "proxy_checker" / "http" / "server_runner.py").read_text(encoding="utf-8")

        self.assertIn("waitress", requirements)
        self.assertIn("from waitress import serve", runner)
        self.assertIn("serve(app, host=\"0.0.0.0\", port=port, threads=threads)", runner)
        self.assertIn("legacy_server()", runner)
        self.assertIn("runtime.main()", server)
        self.assertIn("run_flask_http(", runtime_http)
        self.assertIn("run_legacy_http(", runtime_http)


if __name__ == "__main__":
    unittest.main()
