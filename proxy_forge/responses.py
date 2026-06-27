def error_response(message, **extra):
    payload = {"error": message}
    payload.update(extra)
    return payload


def ok_response(**extra):
    payload = {"ok": True}
    payload.update(extra)
    return payload
