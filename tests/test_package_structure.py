import importlib
import unittest


class PackageStructureTest(unittest.TestCase):
    def test_refactor_target_modules_are_importable(self):
        for module_name in (
            "proxy_checker.models",
            "proxy_checker.responses",
            "proxy_checker.app_dependencies",
            "proxy_checker.app_defaults",
            "proxy_checker.runtime_services",
            "proxy_checker.serverless",
            "proxy_checker.http.blueprints",
            "proxy_checker.http.cors",
            "proxy_checker.checking",
            "proxy_checker.checking.engine",
            "proxy_checker.sources",
            "proxy_checker.sources.fetch",
            "proxy_checker.storage.paths",
        ):
            with self.subTest(module_name=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    def test_checking_and_sources_facades_export_expected_symbols(self):
        checking = importlib.import_module("proxy_checker.checking")
        sources = importlib.import_module("proxy_checker.sources")

        self.assertTrue(hasattr(checking, "ProxyCheckEngine"))
        self.assertTrue(hasattr(checking, "TARGET_PROFILE_OPTIONS"))
        self.assertTrue(hasattr(sources, "PROXY_SOURCES"))
        self.assertTrue(hasattr(sources, "fetch_proxies"))

    def test_legacy_top_level_modules_delegate_to_package_implementations(self):
        legacy_checking = importlib.import_module("proxy_check")
        checking = importlib.import_module("proxy_checker.checking.engine")
        legacy_sources = importlib.import_module("fetch_proxies")
        sources = importlib.import_module("proxy_checker.sources.fetch")

        self.assertIs(legacy_checking.ProxyCheckEngine, checking.ProxyCheckEngine)
        self.assertIs(legacy_checking.CheckConfig, checking.CheckConfig)
        self.assertIs(legacy_sources.PROXY_SOURCES, sources.PROXY_SOURCES)
        self.assertIs(legacy_sources.fetch_proxies, sources.fetch_proxies)


if __name__ == "__main__":
    unittest.main()
