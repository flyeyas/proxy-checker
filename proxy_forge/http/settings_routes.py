from flask import Blueprint, jsonify, make_response

from proxy_forge.http.auth_utils import auth_status_payload, json_request_data, require_auth, set_auth_cookie
from proxy_forge.responses import error_response


def create_settings_blueprint(
    auth_service,
    *,
    capabilities_provider,
    settings_provider,
    server_time_provider,
    save_settings=None,
):
    bp = Blueprint("settings", __name__)

    @bp.post("/api/capabilities")
    def api_capabilities():
        payload = dict(capabilities_provider())
        payload.update(auth_status_payload(auth_service))
        payload["settings"] = settings_provider()
        return jsonify(payload)

    @bp.post("/api/settings/get")
    @require_auth(auth_service)
    def api_settings_get():
        return jsonify({
            "settings": settings_provider(),
            "server_time": server_time_provider(),
        })

    @bp.post("/api/settings/save")
    @require_auth(auth_service)
    def api_settings_save():
        data = json_request_data()
        settings = data.get("settings", {})
        if save_settings is None:
            return jsonify(error_response(
                "当前 Flask 设置路由尚未接入运行时保存逻辑",
                settings=settings_provider(),
            ))
        payload = save_settings(settings)
        response = make_response(jsonify(payload))
        token = payload.get("token") if isinstance(payload, dict) else None
        if token:
            set_auth_cookie(response, auth_service, token)
        return response

    return bp
