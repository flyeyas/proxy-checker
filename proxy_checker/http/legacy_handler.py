import json
import os
import sys
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

from proxy_checker.http.cors import CORS_HEADERS
from proxy_checker.responses import error_response, ok_response
from proxy_checker.utils import proxy_key, sanitize_token


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, logger=None):
        self.logger = logger
        super().__init__(server_address, request_handler_class)

    def handle_error(self, request, client_address):
        exc_type, exc, _ = sys.exc_info()
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            if self.logger:
                self.logger.warning("Client disconnected early", extra={"client_address": client_address})
            return
        super().handle_error(request, client_address)


@dataclass
class LegacyHandlerDependencies:
    root_dir: str
    repo_dir: str
    checked_txt_path: object
    auth_service: object
    runtime_capabilities_payload: object
    public_settings_payload: object
    server_time_payload: object
    save_settings_payload: object
    log_service: object
    start_check_payload: object
    check_status_payload: object
    stop_check_payload: object
    get_auto_payload: object
    save_auto_payload: object
    run_auto_now_payload: object
    stop_auto_payload: object
    auto_status_payload: object
    deep_check_payload: object
    save_repo_payload: object
    fetch_proxies_payload: object
    write_checked_list: object
    read_checked_list: object
    logger: object


def create_legacy_handler(deps):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]

            if path.startswith("/api/repo/") and path.endswith(".json"):
                token = path.split("/")[-1].replace(".json", "")
                json_file = os.path.join(deps.repo_dir, f"{token}.json")
                self._send_public_text_file(json_file, "application/json; charset=utf-8", missing_content="[]")
                return

            if path.startswith("/api/repo/") and path.endswith(".txt"):
                token = path.split("/")[-1].replace(".txt", "")
                repo_file = os.path.join(deps.repo_dir, f"{token}.txt")
                self._send_public_text_file(
                    repo_file,
                    "text/plain; charset=utf-8",
                    missing_status=404,
                    missing_content="Repository not found",
                    missing_cors=False,
                )
                return

            if path.startswith("/api/checked/") and path.endswith(".txt"):
                token = path.split("/")[-1].replace(".txt", "")
                checked_file = deps.checked_txt_path(token)
                self._send_public_text_file(checked_file, "text/plain; charset=utf-8", missing_content="")
                return

            if path == "/login.html":
                self._send_static_file("login.html")
                return

            if path in ("/", "/index.html") and deps.auth_service.is_enabled() and not deps.auth_service.is_request_authenticated(self.headers):
                self._send_static_file("login.html")
                return

            if path == "/app.js" and deps.auth_service.is_enabled() and not deps.auth_service.is_request_authenticated(self.headers):
                self._json(401, error_response("请先输入登录密码", auth_required=True))
                return

            static_files = {
                "/": "index.html",
                "/index.html": "index.html",
                "/app.js": "app.js",
            }
            file_name = static_files.get(path)
            if file_name is None:
                self.send_response(404)
                self.end_headers()
                return
            self._send_static_file(file_name)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}

                if self.path == "/api/auth/status":
                    self._json(200, deps.auth_service.status_payload(
                        deps.auth_service.is_request_authenticated(self.headers),
                    ))

                elif self.path == "/api/auth/login":
                    password = str(body.get("password", ""))
                    if not deps.auth_service.password_matches(password):
                        self._json(401, error_response("密码不正确", auth_required=True))
                        return
                    token = deps.auth_service.make_token()
                    self._json(200, ok_response(
                        token=token,
                        expires_in=deps.auth_service.session_seconds,
                        auth_required=deps.auth_service.is_enabled(),
                    ), [("Set-Cookie", deps.auth_service.make_cookie(token))])

                elif self.path == "/api/auth/logout":
                    self._json(200, ok_response(), [("Set-Cookie", deps.auth_service.make_cookie("", 0))])

                elif self.path == "/api/capabilities":
                    response = deps.runtime_capabilities_payload()
                    response.update(deps.auth_service.status_payload(
                        deps.auth_service.is_request_authenticated(self.headers),
                    ))
                    self._json(200, response)

                elif not deps.auth_service.is_request_authenticated(self.headers):
                    self._json(401, error_response("请先输入登录密码", auth_required=True))

                elif self.path == "/api/settings/get":
                    self._json(200, {"settings": deps.public_settings_payload(), "server_time": deps.server_time_payload()})

                elif self.path == "/api/settings/save":
                    response = deps.save_settings_payload(body.get("settings", {}))
                    if response.get("token"):
                        self._json(200, response, [("Set-Cookie", deps.auth_service.make_cookie(response["token"]))])
                    else:
                        self._json(200, response)

                elif self.path == "/api/logs/list":
                    token = sanitize_token(body.get("token", "default"))
                    self._json(200, deps.log_service.payload(token))

                elif self.path == "/api/logs/clear":
                    token = sanitize_token(body.get("token", "default"))
                    self._json(200, deps.log_service.clear(token))

                elif self.path == "/api/start":
                    self._json(200, deps.start_check_payload(body))

                elif self.path == "/api/status":
                    self._json(200, deps.check_status_payload(body))

                elif self.path == "/api/auto/get":
                    self._json(200, deps.get_auto_payload(body))

                elif self.path == "/api/auto/save":
                    self._json(200, deps.save_auto_payload(body))

                elif self.path == "/api/auto/run-now":
                    self._json(200, deps.run_auto_now_payload(body))

                elif self.path == "/api/auto/stop":
                    self._json(200, deps.stop_auto_payload(body))

                elif self.path == "/api/auto/status":
                    self._json(200, deps.auto_status_payload(body))

                elif self.path == "/api/stop":
                    self._json(200, deps.stop_check_payload(body))

                elif self.path == "/api/deep-check":
                    proxy = body.get("proxy", "")
                    if not proxy:
                        self._json(400, error_response("proxy required"))
                        return
                    self._json(200, deps.deep_check_payload(body))

                elif self.path == "/api/repo/save":
                    repo_data = body.get("repo", None)
                    proxies = body.get("proxies", [])
                    token = body.get("token", "default")
                    if not token.replace("_", "").isalnum():
                        token = "default"
                    mode = body.get("mode", "merge")
                    base_count = body.get("base_count", None)

                    if repo_data is not None:
                        saved, response = deps.save_repo_payload(token, repo_data, mode, base_count)
                        if saved is None:
                            deps.logger.warning("Repo save rejected", extra={"token": token, "response": response})
                            self._json(200, response)
                            return
                        response["url"] = f"/api/repo/{token}.json"
                        deps.logger.info("Repo saved (JSON)", extra={"token": token, "mode": response["mode"], "count": response["count"], "submitted_count": response["submitted_count"]})
                        self._json(200, response)
                    else:
                        legacy_repo = [{"proxy": proxy} for proxy in proxies]
                        saved, response = deps.save_repo_payload(token, legacy_repo, mode, base_count)
                        if saved is None:
                            deps.logger.warning("Repo save rejected", extra={"token": token, "response": response})
                            self._json(200, response)
                            return
                        response["url"] = f"/api/repo/{token}.txt"
                        deps.logger.info("Repo saved (txt)", extra={"token": token, "mode": response["mode"], "count": response["count"], "submitted_count": response["submitted_count"]})
                        self._json(200, response)

                elif self.path == "/api/fetch-proxies":
                    self._json(200, deps.fetch_proxies_payload(body))

                elif self.path == "/api/checked/save":
                    proxies = body.get("proxies", [])
                    token = sanitize_token(body.get("token", "default"))
                    saved = deps.write_checked_list(token, proxies)
                    deps.logger.info(f"Checked proxies saved: token={token}, count={len(saved)}")
                    self._json(200, ok_response(count=len(saved)))

                elif self.path == "/api/checked/filter":
                    proxies = body.get("proxies", [])
                    token = sanitize_token(body.get("token", "default"))
                    checked_set = {proxy_key(proxy) for proxy in deps.read_checked_list(token)}
                    unchecked = [proxy for proxy in proxies if proxy_key(proxy) not in checked_set]
                    skipped = len(proxies) - len(unchecked)
                    self._json(200, {
                        "unchecked": unchecked,
                        "skipped": skipped,
                        "total": len(proxies),
                        "checked_count": len(checked_set),
                    })

                else:
                    self.send_response(404)
                    self.end_headers()

            except Exception as exc:
                deps.logger.error(f"POST error: {exc}")
                try:
                    self._json(500, error_response(str(exc)))
                except Exception:
                    pass

        def do_OPTIONS(self):
            self.send_response(200)
            for key, value in CORS_HEADERS.items():
                self.send_header(key, value)
            self.end_headers()

        def _json(self, code, data, headers=None):
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_bytes(
                code,
                content,
                "application/json; charset=utf-8",
                headers=headers,
                cors=True,
            )

        def _send_public_text_file(
            self,
            file_path,
            content_type,
            missing_status=200,
            missing_content="",
            missing_cors=True,
        ):
            if os.path.isfile(file_path):
                with open(file_path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                self._send_bytes(200, content.encode("utf-8"), content_type, cors=True)
                return
            self._send_bytes(
                missing_status,
                missing_content.encode("utf-8"),
                content_type if missing_cors else None,
                cors=missing_cors,
            )

        def _send_bytes(self, code, content, content_type=None, headers=None, cors=False):
            self.send_response(code)
            if content_type:
                self.send_header("Content-Type", content_type)
            if cors:
                self.send_header("Access-Control-Allow-Origin", CORS_HEADERS["Access-Control-Allow-Origin"])
            for key, value in headers or []:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content)

        def _send_static_file(self, file_name):
            file_path = os.path.join(deps.root_dir, file_name)
            ext = os.path.splitext(file_path)[1]
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".json": "application/json",
            }.get(ext, "application/octet-stream")
            if os.path.isfile(file_path):
                with open(file_path, "rb") as fp:
                    self._send_bytes(200, fp.read(), content_type)
            else:
                self._send_bytes(404, b"")

        def log_message(self, fmt, *args):
            if deps.logger:
                deps.logger.info("%s - %s" % (self.address_string(), fmt % args))

    return Handler
