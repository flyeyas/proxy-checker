from flask import Blueprint, jsonify

from proxy_forge.http.auth_utils import json_request_data, require_auth


def create_fetch_blueprint(auth_service, *, fetch_proxies):
    bp = Blueprint("fetch", __name__)

    @bp.post("/api/fetch-proxies")
    @require_auth(auth_service)
    def api_fetch_proxies():
        return jsonify(fetch_proxies(json_request_data()))

    return bp
