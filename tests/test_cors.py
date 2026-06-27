import unittest

from flask import Flask

from proxy_forge.http.cors import CORS_HEADERS, init_cors


class CorsTest(unittest.TestCase):
    def test_init_cors_adds_standard_headers(self):
        app = Flask(__name__)
        init_cors(app)

        @app.get("/ping")
        def ping():
            return {"ok": True}

        response = app.test_client().get("/ping")

        self.assertEqual(response.status_code, 200)
        for name, value in CORS_HEADERS.items():
            self.assertEqual(response.headers[name], value)


if __name__ == "__main__":
    unittest.main()
