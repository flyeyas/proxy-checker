import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from proxy_checker.services.auth_service import AuthService
from proxy_checker.services.repo_service import RepoService
from proxy_checker.storage.tenant import TenantDirLayout, create_tenant_storage_factory


class FakeLogService:
    def __init__(self):
        self.cleared_tokens = []

    def payload(self, token):
        return {"logs": [{"id": f"{token}-log"}], "count": 1, "server_time": {"timezone": "UTC"}}

    def clear(self, token):
        self.cleared_tokens.append(token)
        return {"ok": True, "logs": [], "count": 0, "server_time": {"timezone": "UTC"}}


@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask is not installed")
class FlaskAppTest(unittest.TestCase):
    def setUp(self):
        from proxy_checker.app import create_app

        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / "index.html").write_text("index", encoding="utf-8")
        (root / "login.html").write_text("login", encoding="utf-8")
        (root / "app.js").write_text("app", encoding="utf-8")

        self.data_dir = root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_factory = create_tenant_storage_factory(TenantDirLayout(str(self.data_dir)))
        self.log_service = FakeLogService()
        self.fetch_requests = []
        self.deep_check_requests = []
        auth_service = AuthService("secret", "signing", 60, "proxy_checker_auth")
        self.app = create_app(
            root_dir=str(root),
            auth_service=auth_service,
            log_service=self.log_service,
            repo_service=RepoService(storage_factory=self.storage_factory),
            deep_check=self.deep_check,
            fetch_proxies=self.fetch_proxies,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def deep_check(self, data):
        self.deep_check_requests.append(dict(data))
        return {"success": True, "proxy": data.get("proxy")}

    def fetch_proxies(self, data):
        self.fetch_requests.append(dict(data))
        return {
            "proxies": [{"proxy": "http://127.0.0.1:8080"}],
            "count": 1,
            "source": "Fake",
            "source_id": data.get("source"),
        }

    def test_static_auth_and_login(self):
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(as_text=True), "login")
        finally:
            response.close()

        response = self.client.get("/app.js")
        try:
            self.assertEqual(response.status_code, 401)
        finally:
            response.close()

        response = self.client.post("/api/auth/login", json={"password": "secret"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.get_json())

        response = self.client.post("/api/start", json={"proxies": []})
        self.assertEqual(response.status_code, 200)
        self.assertIn("尚未接入", response.get_json()["error"])

        response = self.client.post("/api/auto/get", json={"token": "default"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("尚未接入", response.get_json()["error"])

    def test_check_routes_require_auth(self):
        response = self.client.post("/api/start", json={"proxies": []})
        self.assertEqual(response.status_code, 401)

        response = self.client.post("/api/auto/status", json={"token": "default"})
        self.assertEqual(response.status_code, 401)

        response = self.client.post("/api/fetch-proxies", json={"source": "fake"})
        self.assertEqual(response.status_code, 401)

    def test_repo_routes(self):
        token = self.client.post("/api/auth/login", json={"password": "secret"}).get_json()["token"]

        response = self.client.post(
            "/api/repo/save",
            json={"token": "demo", "proxies": ["http://127.0.0.1:8080"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["url"], "/api/repo/demo.txt")

        response = self.client.get("/api/repo/demo.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["proxy"], "http://127.0.0.1:8080")

        response = self.client.get("/api/repo/demo.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "http://127.0.0.1:8080")

        response = self.client.post(
            "/api/checked/save",
            json={"token": "demo", "proxies": ["http://127.0.0.1:8080"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)

        response = self.client.post(
            "/api/checked/filter",
            json={"token": "demo", "proxies": ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["unchecked"], ["http://127.0.0.1:8081"])

    def test_log_routes(self):
        token = self.client.post("/api/auth/login", json={"password": "secret"}).get_json()["token"]

        response = self.client.post(
            "/api/logs/list",
            json={"token": "demo"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)

        response = self.client.post(
            "/api/logs/clear",
            json={"token": "demo"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ok"], True)
        self.assertEqual(self.log_service.cleared_tokens, ["demo"])

    def test_fetch_and_deep_check_routes(self):
        token = self.client.post("/api/auth/login", json={"password": "secret"}).get_json()["token"]

        response = self.client.post(
            "/api/fetch-proxies",
            json={"source": "fake", "limit": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)
        self.assertEqual(self.fetch_requests, [{"source": "fake", "limit": 10}])

        response = self.client.post(
            "/api/deep-check",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/deep-check",
            json={"proxy": "http://127.0.0.1:8080"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["success"], True)
        self.assertEqual(self.deep_check_requests, [{"proxy": "http://127.0.0.1:8080"}])

    def test_create_app_can_skip_repo_routes(self):
        from proxy_checker.app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text("index", encoding="utf-8")
            (root / "login.html").write_text("login", encoding="utf-8")
            (root / "app.js").write_text("app", encoding="utf-8")
            app = create_app(
                root_dir=str(root),
                auth_service=AuthService("secret", "signing", 60, "proxy_checker_auth"),
                deep_check=None,
                include_repo=False,
            )

            response = app.test_client().get("/api/repo/demo.txt")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
