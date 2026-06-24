import importlib.util
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask is not installed")
class ServerlessEntryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "proxy_checker_serverless_index_test",
            root / "api" / "index.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.module = module
        cls.client = module.app.test_client()

    def login_token(self):
        response = self.client.post("/api/auth/login", json={"password": self.module.AUTH_PASSWORD})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    def test_cors_headers_are_shared(self):
        response = self.client.post("/api/auth/status", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("GET", response.headers["Access-Control-Allow-Methods"])
        self.assertIn("X-Proxy-Auth", response.headers["Access-Control-Allow-Headers"])

    def test_capabilities_payload_marks_serverless_hosting(self):
        response = self.client.post("/api/capabilities", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["hosted"], "vercel")
        self.assertEqual(payload["auto_mode"], False)
        self.assertIn("target_profiles", payload)
        self.assertIn("settings", payload)

    def test_unauthorized_response_uses_common_error_payload(self):
        with self.module.app.test_request_context("/api/settings/get"):
            response, status = self.module.unauthorized_response()

        self.assertEqual(status, 401)
        self.assertEqual(response.get_json(), {"error": "请先输入登录密码", "auth_required": True})

    def test_serverless_unsupported_routes_keep_expected_fields(self):
        token = self.login_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.post("/api/settings/save", json={"settings": {}}, headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("Vercel / Serverless", payload["error"])
        self.assertIn("settings", payload)

        response = self.client.post("/api/auto/status", json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["auto_mode"], False)
        self.assertIn("server_time", payload)

    def test_manual_check_routes_use_shared_service(self):
        token = self.login_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.post(
            "/api/start",
            json={"proxies": [], "rounds": 1, "target_profile": "generic", "max_concurrent": 1},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["rounds"], 1)
        self.assertEqual(payload["target_profile"], "generic")

        response = self.client.post(
            "/api/status",
            json={"session_id": payload["session_id"], "since": 0},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("finished", response.get_json())

        response = self.client.post(
            "/api/stop",
            json={"session_id": payload["session_id"]},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_deep_check_is_not_registered_in_serverless(self):
        token = self.login_token()
        response = self.client.post(
            "/api/deep-check",
            json={"proxy": "http://127.0.0.1:8080"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
