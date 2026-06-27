import unittest
from pathlib import Path

from proxy_forge.config import HTTP_THREADS


class EntrypointConfigTest(unittest.TestCase):
    def test_http_threads_is_bounded(self):
        self.assertGreaterEqual(HTTP_THREADS, 1)
        self.assertLessEqual(HTTP_THREADS, 128)

    def test_waitress_dependency_and_entrypoint_are_declared(self):
        root = Path(__file__).resolve().parents[1]
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")
        server = (root / "server.py").read_text(encoding="utf-8")
        runtime_http = (root / "proxy_forge" / "http" / "runtime_http.py").read_text(encoding="utf-8")
        runner = (root / "proxy_forge" / "http" / "server_runner.py").read_text(encoding="utf-8")

        self.assertIn("waitress", requirements)
        self.assertIn("from waitress import serve", runner)
        self.assertIn("serve(app, host=\"0.0.0.0\", port=port, threads=threads)", runner)
        self.assertIn("services.lifecycle_service.start_background_services()", server)
        self.assertIn("services.http_service.serve_flask_http()", server)
        self.assertIn("run_flask_http(", runtime_http)


if __name__ == "__main__":
    unittest.main()
