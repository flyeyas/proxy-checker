import asyncio
import importlib.util
import shutil

from proxy_forge.responses import error_response


DEFAULT_DEEP_CHECK_TARGET = "https://chat.openai.com/"


def is_nodriver_available():
    return importlib.util.find_spec("nodriver") is not None


def unavailable_payload():
    return error_response("nodriver not installed", success=False, hint="pip install nodriver")


def is_xvfb_available():
    return shutil.which("Xvfb") is not None


class DeepCheckService:
    def __init__(self, target_url=DEFAULT_DEEP_CHECK_TARGET, timeout=20, nodriver_module=None):
        self.target_url = target_url or DEFAULT_DEEP_CHECK_TARGET
        self.timeout = timeout
        self._nodriver = nodriver_module

    @property
    def available(self):
        return self._nodriver is not None or is_nodriver_available()

    @property
    def xvfb_available(self):
        return is_xvfb_available()

    def _load_nodriver(self):
        if self._nodriver is None:
            import nodriver
            self._nodriver = nodriver
        return self._nodriver

    async def check_async(self, proxy, target_url=None):
        if not self.available:
            return False, error_response("nodriver not installed")

        nodriver = self._load_nodriver()
        browser = None
        try:
            config = nodriver.Config()
            config.add_argument(f"--proxy-server={proxy}")
            config.add_argument("--no-sandbox")
            config.add_argument("--disable-dev-shm-usage")
            config.headless = True

            browser = await nodriver.start(config=config)
            page = await browser.get(target_url or self.target_url)

            await asyncio.sleep(5)

            title = await page.evaluate("document.title")
            body_text = await page.evaluate("document.body.innerText.substring(0, 2000)")

            cf_detected = False
            cf_type = None
            for indicator in ("Just a moment", "Checking your browser", "Verify you are human", "challenge-platform"):
                if indicator.lower() in body_text.lower():
                    cf_detected = True
                    if "turnstile" in body_text.lower():
                        cf_type = "turnstile"
                    elif "just a moment" in body_text.lower():
                        cf_type = "js"
                    else:
                        cf_type = "managed"
                    break

            has_content = any(keyword in body_text.lower() for keyword in ("chatgpt", "chat.openai.com", "log in", "sign up"))

            return True, {
                "title": title,
                "body_preview": body_text[:500],
                "cf_detected": cf_detected,
                "cf_type": cf_type,
                "has_real_content": has_content,
                "success": has_content and not cf_detected,
            }
        except Exception as exc:
            return False, error_response(str(exc)[:200])
        finally:
            if browser:
                try:
                    await browser.stop()
                except Exception:
                    pass

    def check(self, proxy, target_url=None):
        if not self.available:
            return error_response("nodriver not installed", success=False)

        loop = asyncio.new_event_loop()
        try:
            ok, details = loop.run_until_complete(self.check_async(proxy, target_url or self.target_url))
            return {"success": ok, **details}
        finally:
            loop.close()

    def payload(self, data):
        proxy = data.get("proxy", "")
        if not proxy:
            return error_response("proxy required")
        if not self.available:
            return unavailable_payload()
        return self.check(proxy, data.get("target", self.target_url))
