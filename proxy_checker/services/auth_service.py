import hashlib
import hmac
import time
from http import cookies

from proxy_checker.config import AUTH_COOKIE_NAME


class AuthService:
    def __init__(self, password, session_secret, session_seconds, cookie_name):
        self.configure(password, session_secret, session_seconds)
        self.cookie_name = cookie_name

    def configure(self, password=None, session_secret=None, session_seconds=None):
        if password is not None:
            self.password = str(password)
        if session_secret is not None:
            self.session_secret = str(session_secret)
        if session_seconds is not None:
            self.session_seconds = max(1, int(session_seconds))

    def is_enabled(self):
        return bool(self.password)

    def status_payload(self, authenticated):
        return {
            "authenticated": bool(authenticated),
            "auth_required": self.is_enabled(),
        }

    def password_matches(self, password):
        return hmac.compare_digest(str(password or ""), self.password)

    def make_token(self):
        issued_at = str(int(time.time()))
        signature = hmac.new(
            self.session_secret.encode("utf-8"),
            issued_at.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{issued_at}:{signature}"

    def verify_token(self, token):
        if not self.is_enabled():
            return True
        try:
            issued_at, signature = str(token or "").split(":", 1)
            issued_at_int = int(issued_at)
        except (TypeError, ValueError):
            return False
        if time.time() - issued_at_int > self.session_seconds:
            return False
        expected = hmac.new(
            self.session_secret.encode("utf-8"),
            issued_at.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    @staticmethod
    def bearer_token(headers):
        auth_header = headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return headers.get("X-Proxy-Auth", "").strip()

    def cookie_token(self, cookie_header):
        parsed = cookies.SimpleCookie()
        try:
            parsed.load(cookie_header or "")
        except cookies.CookieError:
            return ""
        morsel = parsed.get(self.cookie_name)
        return morsel.value if morsel else ""

    def is_request_authenticated(self, headers):
        token = self.bearer_token(headers) or self.cookie_token(headers.get("Cookie", ""))
        return self.verify_token(token)

    def make_cookie(self, token, max_age=None):
        age = self.session_seconds if max_age is None else max(0, int(max_age))
        return f"{self.cookie_name}={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax"


def create_runtime_auth_service(state, cookie_name=AUTH_COOKIE_NAME):
    return AuthService(
        state.auth_password,
        state.auth_session_secret,
        state.auth_session_seconds,
        cookie_name,
    )
