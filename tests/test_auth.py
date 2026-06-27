import time
import unittest
from types import SimpleNamespace

from proxy_forge.config import AUTH_COOKIE_NAME
from proxy_forge.services.auth_service import AuthService, create_runtime_auth_service


class AuthServiceTest(unittest.TestCase):
    def test_password_and_token(self):
        auth = AuthService("secret", "signing", 60, "proxy_forge_auth")
        self.assertTrue(auth.is_enabled())
        self.assertTrue(auth.password_matches("secret"))
        self.assertFalse(auth.password_matches("wrong"))

        token = auth.make_token()
        self.assertTrue(auth.verify_token(token))
        self.assertFalse(auth.verify_token("bad-token"))

    def test_status_payload(self):
        auth = AuthService("secret", "signing", 60, "proxy_forge_auth")

        self.assertEqual(auth.status_payload(True), {"authenticated": True, "auth_required": True})
        self.assertEqual(auth.status_payload(False), {"authenticated": False, "auth_required": True})

    def test_disabled_auth_allows_request(self):
        auth = AuthService("", "signing", 60, "proxy_forge_auth")
        self.assertFalse(auth.is_enabled())
        self.assertTrue(auth.verify_token(""))
        self.assertEqual(auth.status_payload(True), {"authenticated": True, "auth_required": False})

    def test_headers_and_cookie_token(self):
        auth = AuthService("secret", "signing", 60, "proxy_forge_auth")
        self.assertEqual(auth.bearer_token({"Authorization": "Bearer abc"}), "abc")
        self.assertEqual(auth.bearer_token({"X-Proxy-Auth": "xyz"}), "xyz")
        self.assertEqual(auth.cookie_token("proxy_forge_auth=cookie-token"), "cookie-token")

    def test_expired_token_rejected(self):
        auth = AuthService("secret", "signing", 1, "proxy_forge_auth")
        issued_at = str(int(time.time()) - 10)
        expired = f"{issued_at}:bad-signature"
        self.assertFalse(auth.verify_token(expired))

    def test_create_runtime_auth_service_uses_runtime_state(self):
        auth = create_runtime_auth_service(SimpleNamespace(
            auth_password="secret",
            auth_session_secret="signing",
            auth_session_seconds=60,
        ))

        self.assertTrue(auth.password_matches("secret"))
        self.assertEqual(auth.session_secret, "signing")
        self.assertEqual(auth.session_seconds, 60)
        self.assertEqual(auth.cookie_name, AUTH_COOKIE_NAME)


if __name__ == "__main__":
    unittest.main()
