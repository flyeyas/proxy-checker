from flask import Blueprint, Response, jsonify

from proxy_checker.http.auth_utils import json_request_data, require_auth
from proxy_checker.services.repo_service import (
    RepoService,
    read_checked_list as default_read_checked_list,
    read_repo_data as default_read_repo_data,
    save_repo_payload as default_save_repo_payload,
    write_checked_list as default_write_checked_list,
    write_repo_data as default_write_repo_data,
)


def create_repo_blueprint(
    auth_service,
    *,
    repo_service=None,
    read_repo_data=None,
    save_repo_payload=None,
    write_repo_data=None,
    read_checked_list=None,
    write_checked_list=None,
):
    bp = Blueprint("repo", __name__)
    repo_service = repo_service or RepoService(
        read_repo_func=read_repo_data or default_read_repo_data,
        save_repo_func=save_repo_payload or default_save_repo_payload,
        write_repo_func=write_repo_data or default_write_repo_data,
        read_checked_func=read_checked_list or default_read_checked_list,
        write_checked_func=write_checked_list or default_write_checked_list,
    )

    @bp.get("/api/repo/<token>.json")
    def api_repo_json(token):
        return jsonify(repo_service.repo_json(token))

    @bp.get("/api/repo/<token>.txt")
    def api_repo_txt(token):
        return Response(repo_service.repo_text(token), mimetype="text/plain; charset=utf-8")

    @bp.get("/api/checked/<token>.txt")
    def api_checked_txt(token):
        return Response(repo_service.checked_text(token), mimetype="text/plain; charset=utf-8")

    @bp.post("/api/repo/save")
    @require_auth(auth_service)
    def api_repo_save():
        return jsonify(repo_service.save(json_request_data()))

    @bp.post("/api/repo/load")
    @require_auth(auth_service)
    def api_repo_load():
        return jsonify(repo_service.load(json_request_data()))

    @bp.post("/api/repo/clear")
    @require_auth(auth_service)
    def api_repo_clear():
        return jsonify(repo_service.clear(json_request_data()))

    @bp.post("/api/checked/save")
    @require_auth(auth_service)
    def api_checked_save():
        return jsonify(repo_service.save_checked(json_request_data()))

    @bp.post("/api/checked/filter")
    @require_auth(auth_service)
    def api_checked_filter():
        return jsonify(repo_service.filter_checked(json_request_data()))

    return bp
