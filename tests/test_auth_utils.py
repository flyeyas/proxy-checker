import unittest

from flask import Flask, make_response

from proxy_checker.http.auth_utils import auth_status_payload, require_auth, set_auth_cookie
from proxy_checker.services.auth_service import AuthService


class AuthUtilsTest(unittest.TestCase):
    def setUp(self):
        self.auth_service = AuthService("secret", "signing", 60, "proxy_checker_auth")
        self.app = Flask(__name__)

        @self.app.post("/protected")
        @require_auth(self.auth_service)
        def protected():
            return {"ok": True}

        @self.app.post("/status")
        def status():
            return auth_status_payload(self.auth_service)

        @self.app.post("/cookie")
        def cookie():
            response = make_response({"ok": True})
            return set_auth_cookie(response, self.auth_service, "token-value", 0)

        self.client = self.app.test_client()

    def test_require_auth_rejects_unauthenticated_request(self):
        response = self.client.post("/protected", json={})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "请先输入登录密码", "auth_required": True})

    def test_require_auth_allows_bearer_token(self):
        token = self.auth_service.make_token()

        response = self.client.post("/protected", headers={"Authorization": f"Bearer {token}"}, json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_auth_status_payload_uses_request_token(self):
        token = self.auth_service.make_token()

        response = self.client.post("/status", headers={"Authorization": f"Bearer {token}"}, json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"authenticated": True, "auth_required": True})

    def test_set_auth_cookie_uses_auth_service_settings(self):
        response = self.client.post("/cookie", json={})

        self.assertEqual(response.status_code, 200)
        self.assertIn("proxy_checker_auth=token-value", response.headers["Set-Cookie"])
        self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
