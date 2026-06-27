import importlib
import unittest


class PackageStructureTest(unittest.TestCase):
    def test_refactor_target_modules_are_importable(self):
        for module_name in (
            "proxy_forge.models",
            "proxy_forge.responses",
            "proxy_forge.app_dependencies",
            "proxy_forge.app_defaults",
            "proxy_forge.runtime_services",
            "proxy_forge.serverless",
            "proxy_forge.http.blueprints",
            "proxy_forge.http.cors",
            "proxy_forge.checking",
            "proxy_forge.checking.engine",
            "proxy_forge.sources",
            "proxy_forge.sources.fetch",
            "proxy_forge.storage.paths",
        ):
            with self.subTest(module_name=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    def test_checking_and_sources_facades_export_expected_symbols(self):
        checking = importlib.import_module("proxy_forge.checking")
        sources = importlib.import_module("proxy_forge.sources")

        self.assertTrue(hasattr(checking, "ProxyCheckEngine"))
        self.assertTrue(hasattr(checking, "TARGET_PROFILE_OPTIONS"))
        self.assertTrue(hasattr(sources, "PROXY_SOURCES"))
        self.assertTrue(hasattr(sources, "fetch_proxies"))

    def test_legacy_top_level_modules_delegate_to_package_implementations(self):
        legacy_checking = importlib.import_module("proxy_check")
        checking = importlib.import_module("proxy_forge.checking.engine")
        legacy_sources = importlib.import_module("fetch_proxies")
        sources = importlib.import_module("proxy_forge.sources.fetch")

        self.assertIs(legacy_checking.ProxyCheckEngine, checking.ProxyCheckEngine)
        self.assertIs(legacy_checking.CheckConfig, checking.CheckConfig)
        self.assertIs(legacy_sources.PROXY_SOURCES, sources.PROXY_SOURCES)
        self.assertIs(legacy_sources.fetch_proxies, sources.fetch_proxies)


if __name__ == "__main__":
    unittest.main()
