import unittest
from types import SimpleNamespace

from proxy_forge.services.fetch_service import ProxyFetchService


class ProxyFetchServiceTest(unittest.TestCase):
    def test_default_module_uses_sources_package(self):
        service = ProxyFetchService()

        self.assertEqual(service.module_name, "proxy_forge.sources.fetch")
        self.assertTrue(service.available)
        self.assertTrue(service.sources())

    def test_unavailable_module_returns_error_payload(self):
        service = ProxyFetchService("missing_proxy_fetch_module")

        payload = service.payload({"source": "demo"})

        self.assertEqual(payload["error"], "fetch_proxies 模块不可用")
        self.assertIsNone(payload["source"])
        self.assertEqual(service.sources(), [])
        self.assertFalse(service.available)

    def test_sources_are_exposed_from_loaded_module(self):
        service = ProxyFetchService()
        service._module = SimpleNamespace(
            PROXY_SOURCES=[{"id": "demo", "name": "Demo Source"}],
            fetch_proxies=lambda source_id, limit: ([], "Demo Source", None),
        )

        self.assertTrue(service.available)
        self.assertEqual(service.sources(), [{"id": "demo", "name": "Demo Source"}])

    def test_payload_fetches_and_normalizes_limit(self):
        calls = []

        def fetch_proxies(source_id, limit):
            calls.append((source_id, limit))
            return ([{"proxy": "http://127.0.0.1:8080"}], "Demo Source", None)

        service = ProxyFetchService()
        service._module = SimpleNamespace(PROXY_SOURCES=[], fetch_proxies=fetch_proxies)

        payload = service.payload({"source": "demo", "limit": "not-a-number"})

        self.assertEqual(calls, [("demo", 999999)])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["source_id"], "demo")


if __name__ == "__main__":
    unittest.main()
