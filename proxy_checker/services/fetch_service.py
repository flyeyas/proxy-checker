import importlib

from proxy_checker.responses import error_response


class ProxyFetchService:
    def __init__(self, module_name="proxy_checker.sources.fetch"):
        self.module_name = module_name
        self._module = None
        self._load_error = None

    def _load_module(self):
        if self._module is not None:
            return self._module
        if self._load_error is not None:
            return None
        try:
            self._module = importlib.import_module(self.module_name)
        except ImportError as exc:
            self._load_error = exc
            return None
        return self._module

    @property
    def available(self):
        module = self._load_module()
        return module is not None and hasattr(module, "fetch_proxies")

    def sources(self):
        module = self._load_module()
        if module is None:
            return []
        return [
            {"id": source["id"], "name": source["name"]}
            for source in getattr(module, "PROXY_SOURCES", [])
        ]

    def fetch(self, source_id, limit):
        module = self._load_module()
        if module is None or not hasattr(module, "fetch_proxies"):
            return [], None, "fetch_proxies 模块不可用"
        return module.fetch_proxies(source_id, limit)

    def payload(self, data):
        source_id = data.get("source", "proxifly")
        try:
            limit = min(int(data.get("limit", 999999)), 999999)
        except (TypeError, ValueError):
            limit = 999999
        proxies, source_name, error = self.fetch(source_id, limit)
        if error:
            return error_response(error, source=source_name)
        return {
            "proxies": proxies,
            "count": len(proxies),
            "source": source_name,
            "source_id": source_id,
        }
