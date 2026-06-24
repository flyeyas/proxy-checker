import unittest

from proxy_checker.responses import error_response, ok_response


class ResponsesTest(unittest.TestCase):
    def test_error_response_merges_extra_fields(self):
        self.assertEqual(
            error_response("failed", auth_required=True),
            {"error": "failed", "auth_required": True},
        )

    def test_ok_response_merges_extra_fields(self):
        self.assertEqual(ok_response(count=2), {"ok": True, "count": 2})


if __name__ == "__main__":
    unittest.main()
