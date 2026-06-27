def sanitize_token(value):
    token = str(value or "default").strip()
    if token.replace("_", "").isalnum():
        return token
    return "default"


def proxy_key(value):
    return str(value or "").strip().lower()


def normalize_proxy_list(items):
    out = []
    seen = set()
    for item in items or []:
        if isinstance(item, dict):
            proxy = str(item.get("proxy", "")).strip()
        else:
            proxy = str(item or "").strip()
        if not proxy:
            continue
        key = proxy_key(proxy)
        if key in seen:
            continue
        seen.add(key)
        out.append(proxy)
    return out
