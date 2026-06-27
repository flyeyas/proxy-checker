from flask import Blueprint, abort, send_from_directory

from proxy_forge.http.auth_utils import is_authenticated, unauthorized_response


def create_static_blueprint(root_dir, auth_service):
    bp = Blueprint("static_pages", __name__)

    @bp.get("/")
    def index():
        if auth_service.is_enabled() and not is_authenticated(auth_service):
            return send_from_directory(root_dir, "login.html")
        return send_from_directory(root_dir, "index.html")

    @bp.route("/api/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def missing_api(path):
        abort(404)

    @bp.get("/<path:path>")
    def static_files(path):
        if path == "login.html":
            return send_from_directory(root_dir, path)
        if path == "index.html" and auth_service.is_enabled() and not is_authenticated(auth_service):
            return send_from_directory(root_dir, "login.html")
        if path == "app.js" and auth_service.is_enabled() and not is_authenticated(auth_service):
            return unauthorized_response()
        if path in ("index.html", "app.js"):
            return send_from_directory(root_dir, path)
        abort(404)

    return bp
