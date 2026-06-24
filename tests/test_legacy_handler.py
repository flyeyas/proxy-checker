import io
import json
import tempfile
import unittest
from pathlib import Path

from proxy_checker.http.legacy_handler import (
    LegacyHandlerDependencies,
    create_legacy_handler,
)
from proxy_checker.services.auth_service import AuthService


class LegacyHandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.root = root
        self.repo_dir = root / "repo"
        self.checked_dir = root / "checked"
        self.repo_dir.mkdir()
        self.checked_dir.mkdir()
        (root / "index.html").write_text("index", encoding="utf-8")
        (root / "login.html").write_text("login", encoding="utf-8")
        (root / "app.js").write_text("app", encoding="utf-8")
        (self.repo_dir / "demo.json").write_text('[{"proxy":"http://127.0.0.1:8080"}]', encoding="utf-8")
        (self.repo_dir / "demo.txt").write_text("http://127.0.0.1:8080", encoding="utf-8")
        self.auth_service = AuthService("secret", "signing", 60, "proxy_checker_auth")
        self.handler = create_legacy_handler(self.dependencies())

    def tearDown(self):
        self.temp_dir.cleanup()

    def dependencies(self):
        return LegacyHandlerDependencies(
            root_dir=str(self.root),
            repo_dir=str(self.repo_dir),
            checked_txt_path=lambda token: str(self.checked_dir / f"{token}.txt"),
            auth_service=self.auth_service,
            runtime_capabilities_payload=lambda: {"auto_mode": True},
            public_settings_payload=lambda: {"check_rounds": 2},
            server_time_payload=lambda: {"timezone": "UTC"},
            save_settings_payload=lambda _settings: {"ok": True},
            log_service=FakeLogService(),
            start_check_payload=lambda _body: {"session_id": "session"},
            check_status_payload=lambda _body: {"total": 0},
            stop_check_payload=lambda _body: {"ok": True},
            get_auto_payload=lambda _body: {"state": {"status": "idle"}},
            save_auto_payload=lambda _body: {"saved": True},
            run_auto_now_payload=lambda _body: {"started": True},
            stop_auto_payload=lambda _body: {"stopped": True},
            auto_status_payload=lambda _body: {"state": {"status": "idle"}},
            deep_check_payload=lambda body: {"success": True, "proxy": body.get("proxy")},
            save_repo_payload=lambda *_args: ([], {"ok": True, "mode": "merge", "count": 0, "submitted_count": 0}),
            fetch_proxies_payload=lambda _body: {"proxies": [], "count": 0},
            write_checked_list=lambda _token, proxies: list(proxies),
            read_checked_list=lambda _token: ["http://127.0.0.1:8080"],
            logger=FakeLogger(),
        )

    def request(self, method, path, body=None, headers=None):
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            request_headers["Content-Length"] = str(len(payload))
        request = self.build_request(method, path, payload, request_headers)
        socket = FakeSocket(request)
        self.handler(socket, ("127.0.0.1", 12345), object())
        return parse_response(socket.output.getvalue())

    @staticmethod
    def build_request(method, path, payload, headers):
        lines = [f"{method} {path} HTTP/1.1", "Host: localhost"]
        for key, value in headers.items():
            lines.append(f"{key}: {value}")
        head = "\r\n".join(lines).encode("utf-8") + b"\r\n\r\n"
        return head + (payload or b"")

    def test_static_auth_and_public_repo_links(self):
        response, data = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertEqual(data.decode("utf-8"), "login")

        response, data = self.request("GET", "/app.js")
        self.assertEqual(response.status, 401)
        self.assertEqual(json.loads(data.decode("utf-8"))["auth_required"], True)

        response, data = self.request("GET", "/api/repo/demo.json")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data.decode("utf-8"))[0]["proxy"], "http://127.0.0.1:8080")

        response, data = self.request("GET", "/api/repo/demo.txt")
        self.assertEqual(response.status, 200)
        self.assertEqual(data.decode("utf-8"), "http://127.0.0.1:8080")

    def test_login_sets_cookie(self):
        response, data = self.request("POST", "/api/auth/login", {"password": "secret"})

        self.assertEqual(response.status, 200)
        self.assertIn("Set-Cookie", response.headers)
        self.assertIn("token", json.loads(data.decode("utf-8")))

    def test_public_repo_missing_fallbacks(self):
        response, data = self.request("GET", "/api/repo/missing.json")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(json.loads(data.decode("utf-8")), [])

        response, data = self.request("GET", "/api/repo/missing.txt")
        self.assertEqual(response.status, 404)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(data.decode("utf-8"), "Repository not found")

        response, data = self.request("GET", "/api/checked/missing.txt")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(data.decode("utf-8"), "")

    def test_options_uses_shared_cors_headers(self):
        response, data = self.request("OPTIONS", "/api/start")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("GET", response.headers["Access-Control-Allow-Methods"])
        self.assertIn("X-Proxy-Auth", response.headers["Access-Control-Allow-Headers"])
        self.assertEqual(data, b"")

    def test_deep_check_requires_proxy(self):
        token = self.auth_service.make_token()
        response, data = self.request(
            "POST",
            "/api/deep-check",
            {},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(data.decode("utf-8"))["error"], "proxy required")

    def test_checked_save_uses_ok_payload(self):
        token = self.auth_service.make_token()
        response, data = self.request(
            "POST",
            "/api/checked/save",
            {"token": "demo", "proxies": ["http://127.0.0.1:8080"]},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data.decode("utf-8")), {"ok": True, "count": 1})


class FakeLogService:
    def payload(self, token):
        return {"logs": [{"id": token}], "count": 1}

    def clear(self, token):
        return {"ok": True, "logs": [], "count": 0}


class FakeLogger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class FakeSocket:
    def __init__(self, request):
        self.input = NonClosingBytesIO(request)
        self.output = NonClosingBytesIO()

    def makefile(self, mode, *_args, **_kwargs):
        return self.input if "r" in mode else self.output

    def sendall(self, data):
        self.output.write(data)


class NonClosingBytesIO(io.BytesIO):
    def close(self):
        pass


class ParsedResponse:
    def __init__(self, status, headers):
        self.status = status
        self.headers = headers


def parse_response(raw):
    head, body = raw.split(b"\r\n\r\n", 1)
    lines = head.decode("iso-8859-1").split("\r\n")
    status = int(lines[0].split(" ", 2)[1])
    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key] = value.strip()
    return ParsedResponse(status, headers), body


if __name__ == "__main__":
    unittest.main()
