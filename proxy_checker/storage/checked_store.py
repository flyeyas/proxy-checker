import os

from proxy_checker.config import CHECKED_DIR
from proxy_checker.storage.files import atomic_write_text
from proxy_checker.utils import normalize_proxy_list, proxy_key, sanitize_token


def checked_txt_path(token):
    return os.path.join(CHECKED_DIR, f"{sanitize_token(token)}.txt")


def read_checked_list(token):
    path = checked_txt_path(token)
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def write_checked_list(token, proxies):
    proxies = normalize_proxy_list(proxies)
    atomic_write_text(checked_txt_path(token), "\n".join(proxies))
    return proxies


def append_checked_list(token, proxies):
    existing = read_checked_list(token)
    seen = {proxy_key(proxy) for proxy in existing}
    merged = list(existing)
    for proxy in normalize_proxy_list(proxies):
        key = proxy_key(proxy)
        if key not in seen:
            seen.add(key)
            merged.append(proxy)
    return write_checked_list(token, merged)
