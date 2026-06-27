import unittest
from unittest.mock import patch

from proxy_forge.services.deep_check_service import DeepCheckService, unavailable_payload


class DeepCheckServiceTest(unittest.TestCase):
    def test_payload_returns_hint_when_nodriver_unavailable(self):
        service = DeepCheckService(nodriver_module=None)

        with patch("proxy_forge.services.deep_check_service.is_nodriver_available", return_value=False):
            self.assertEqual(service.payload({"proxy": "http://127.0.0.1:8080"}), unavailable_payload())

    def test_payload_requires_proxy(self):
        service = DeepCheckService(nodriver_module=FakeNodriver("ChatGPT log in"))

        self.assertEqual(service.payload({}), {"error": "proxy required"})

    def test_xvfb_availability_is_exposed(self):
        service = DeepCheckService(nodriver_module=FakeNodriver("ChatGPT log in"))

        with patch("proxy_forge.services.deep_check_service.is_xvfb_available", return_value=True):
            self.assertTrue(service.xvfb_available)

    def test_check_reports_real_content_without_cloudflare_challenge(self):
        fake_nodriver = FakeNodriver("ChatGPT log in")
        service = DeepCheckService(target_url="https://example.test/", nodriver_module=fake_nodriver)

        with patch("proxy_forge.services.deep_check_service.asyncio.sleep", new=fake_sleep):
            result = service.check("http://127.0.0.1:8080")

        self.assertEqual(result["success"], True)
        self.assertEqual(result["title"], "Fake Page")
        self.assertEqual(result["has_real_content"], True)
        self.assertEqual(result["cf_detected"], False)
        self.assertEqual(fake_nodriver.last_config.arguments[0], "--proxy-server=http://127.0.0.1:8080")
        self.assertEqual(fake_nodriver.last_target, "https://example.test/")

    def test_check_detects_cloudflare_challenge(self):
        service = DeepCheckService(nodriver_module=FakeNodriver("Just a moment Verify you are human"))

        with patch("proxy_forge.services.deep_check_service.asyncio.sleep", new=fake_sleep):
            result = service.check("http://127.0.0.1:8080")

        self.assertEqual(result["success"], False)
        self.assertEqual(result["cf_detected"], True)


async def fake_sleep(_seconds):
    return None


class FakeConfig:
    def __init__(self):
        self.arguments = []
        self.headless = False

    def add_argument(self, value):
        self.arguments.append(value)


class FakePage:
    def __init__(self, body_text):
        self.body_text = body_text

    async def evaluate(self, script):
        if script == "document.title":
            return "Fake Page"
        return self.body_text


class FakeBrowser:
    def __init__(self, nodriver, body_text):
        self.nodriver = nodriver
        self.body_text = body_text
        self.stopped = False

    async def get(self, target_url):
        self.nodriver.last_target = target_url
        return FakePage(self.body_text)

    async def stop(self):
        self.stopped = True


class FakeNodriver:
    def __init__(self, body_text):
        self.body_text = body_text
        self.last_config = None
        self.last_target = None

    def Config(self):
        self.last_config = FakeConfig()
        return self.last_config

    async def start(self, config):
        self.last_config = config
        return FakeBrowser(self, self.body_text)


if __name__ == "__main__":
    unittest.main()
