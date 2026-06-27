from flask import Blueprint, jsonify

from proxy_forge.http.auth_utils import json_request_data, require_auth


def create_auto_blueprint(auth_service, *, get_auto, save_auto, run_auto_now, stop_auto, status_auto):
    bp = Blueprint("auto", __name__)

    @bp.post("/api/auto/get")
    @require_auth(auth_service)
    def api_auto_get():
        return jsonify(get_auto(json_request_data()))

    @bp.post("/api/auto/save")
    @require_auth(auth_service)
    def api_auto_save():
        return jsonify(save_auto(json_request_data()))

    @bp.post("/api/auto/run-now")
    @require_auth(auth_service)
    def api_auto_run_now():
        return jsonify(run_auto_now(json_request_data()))

    @bp.post("/api/auto/stop")
    @require_auth(auth_service)
    def api_auto_stop():
        return jsonify(stop_auto(json_request_data()))

    @bp.post("/api/auto/status")
    @require_auth(auth_service)
    def api_auto_status():
        return jsonify(status_auto(json_request_data()))

    return bp
