from flask import Blueprint, jsonify

from proxy_forge.http.auth_utils import json_request_data, require_auth
from proxy_forge.responses import error_response


def create_check_blueprint(auth_service, *, start_check, get_status, stop_check, deep_check):
    bp = Blueprint("check", __name__)

    @bp.post("/api/start")
    @require_auth(auth_service)
    def api_start():
        return jsonify(start_check(json_request_data()))

    @bp.post("/api/status")
    @require_auth(auth_service)
    def api_status():
        return jsonify(get_status(json_request_data()))

    @bp.post("/api/stop")
    @require_auth(auth_service)
    def api_stop():
        return jsonify(stop_check(json_request_data()))

    if deep_check is not None:
        @bp.post("/api/deep-check")
        @require_auth(auth_service)
        def api_deep_check():
            data = json_request_data()
            if not data.get("proxy"):
                return jsonify(error_response("proxy required")), 400
            return jsonify(deep_check(data))

    return bp
