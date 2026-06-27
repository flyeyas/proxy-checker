from flask import Blueprint, jsonify

from proxy_forge.http.auth_utils import json_request_data, require_auth
from proxy_forge.utils import sanitize_token


def create_log_blueprint(auth_service, *, log_service):
    bp = Blueprint("logs", __name__)

    @bp.post("/api/logs/list")
    @require_auth(auth_service)
    def api_logs_list():
        token = sanitize_token(json_request_data().get("token", "default"))
        return jsonify(log_service.payload(token))

    @bp.post("/api/logs/clear")
    @require_auth(auth_service)
    def api_logs_clear():
        token = sanitize_token(json_request_data().get("token", "default"))
        return jsonify(log_service.clear(token))

    return bp
