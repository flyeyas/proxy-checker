from flask import Blueprint, jsonify, make_response, request

from proxy_forge.http.auth_utils import auth_status_payload, set_auth_cookie
from proxy_forge.responses import error_response, ok_response


def create_auth_blueprint(auth_service):
    bp = Blueprint("auth", __name__)

    @bp.post("/api/auth/status")
    def api_auth_status():
        return jsonify(auth_status_payload(auth_service))

    @bp.post("/api/auth/login")
    def api_auth_login():
        data = request.get_json(force=True) or {}
        password = str(data.get("password", ""))
        if not auth_service.password_matches(password):
            return jsonify(error_response("密码不正确", auth_required=True)), 401

        token = auth_service.make_token()
        response = make_response(jsonify(ok_response(
            token=token,
            expires_in=auth_service.session_seconds,
            auth_required=auth_service.is_enabled(),
        )))
        return set_auth_cookie(response, auth_service, token)

    @bp.post("/api/auth/logout")
    def api_auth_logout():
        response = make_response(jsonify(ok_response()))
        return set_auth_cookie(response, auth_service, "", 0)

    return bp
