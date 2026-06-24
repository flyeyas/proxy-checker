from functools import wraps

from flask import jsonify, request

from proxy_checker.responses import error_response


def is_authenticated(auth_service):
    token = auth_service.bearer_token(request.headers) or request.cookies.get(auth_service.cookie_name, "")
    return auth_service.verify_token(token)


def unauthorized_response():
    return jsonify(error_response("请先输入登录密码", auth_required=True)), 401


def auth_status_payload(auth_service):
    return auth_service.status_payload(is_authenticated(auth_service))


def set_auth_cookie(response, auth_service, token, max_age=None):
    cookie_age = auth_service.session_seconds if max_age is None else max(0, int(max_age))
    response.set_cookie(
        auth_service.cookie_name,
        token,
        max_age=cookie_age,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


def require_auth(auth_service):
    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            if not is_authenticated(auth_service):
                return unauthorized_response()
            return handler(*args, **kwargs)

        return wrapper

    return decorator


def json_request_data():
    return request.get_json(force=True) or {}
