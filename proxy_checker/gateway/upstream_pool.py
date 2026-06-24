import base64
import os
import threading
from urllib.parse import unquote, urlsplit

from proxy_checker.services.repo_service import filter_repo_by_grades
from proxy_checker.storage.repo_store import read_repo_data
from proxy_checker.utils import sanitize_token


def parse_allowed_grades(grades):
    parsed = {
        str(item).strip().upper()
        for item in str(grades or "").replace(";", ",").split(",")
        if str(item).strip()
    }
    return parsed or {"A", "B"}


def choose_upstream(candidates, current_index):
    if not candidates:
        return [], 0
    start = int(current_index or 0) % len(candidates)
    next_index = (start + 1) % len(candidates)
    return candidates[start:] + candidates[:start], next_index


class ProxyGatewayUpstreamPool:
    def __init__(self, repo_dir, token="", grades="A,B", read_repo=read_repo_data):
        self.repo_dir = repo_dir
        self.token = str(token or "").strip()
        self.grades = str(grades or "A,B")
        self.read_repo = read_repo
        self._lock = threading.Lock()
        self._index = 0

    def allowed_grades(self):
        return parse_allowed_grades(self.grades)

    def repo_tokens(self):
        if self.token:
            return [sanitize_token(self.token)]
        tokens = set()
        if not os.path.isdir(self.repo_dir):
            return []
        for name in os.listdir(self.repo_dir):
            base, ext = os.path.splitext(name)
            if ext in (".json", ".txt") and base:
                tokens.add(sanitize_token(base))
        return sorted(tokens)

    @staticmethod
    def normalize_upstream_proxy(value):
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = raw if "://" in raw else f"http://{raw}"
        parsed = urlsplit(candidate)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None
        host = parsed.hostname
        port = parsed.port or (443 if scheme == "https" else 80)
        if not host or not port:
            return None
        auth = ""
        if parsed.username:
            user = unquote(parsed.username or "")
            password = unquote(parsed.password or "")
            token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
            auth = f"Proxy-Authorization: Basic {token}\r\n"
        return {
            "raw": raw,
            "scheme": scheme,
            "host": host,
            "port": port,
            "auth": auth,
        }

    def candidates(self):
        allowed_grades = self.allowed_grades()
        candidates = []
        seen = set()
        for token in self.repo_tokens():
            for item in filter_repo_by_grades(self.read_repo(token), allowed_grades):
                upstream = self.normalize_upstream_proxy(item.get("proxy"))
                if not upstream:
                    continue
                key = f"{upstream['scheme']}://{upstream['host']}:{upstream['port']}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(upstream)
        return candidates

    def ordered_candidates(self):
        candidates = self.candidates()
        if not candidates:
            return []
        with self._lock:
            ordered, self._index = choose_upstream(candidates, self._index)
        return ordered


ProxyGatewayService = ProxyGatewayUpstreamPool
