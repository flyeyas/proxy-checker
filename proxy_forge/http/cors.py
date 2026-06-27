CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Proxy-Auth",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}


def add_cors_headers(response):
    for name, value in CORS_HEADERS.items():
        response.headers[name] = value
    return response


def init_cors(app):
    app.after_request(add_cors_headers)
    return app
