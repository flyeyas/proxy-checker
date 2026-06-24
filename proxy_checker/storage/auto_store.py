from proxy_checker.config import AUTO_DIR
from proxy_checker.storage.files import atomic_write_json, read_json_file
from proxy_checker.storage.paths import list_token_files, token_file_path


def auto_json_path(token):
    return token_file_path(AUTO_DIR, token, "json")


def list_auto_tokens():
    return list_token_files(AUTO_DIR, "json")


def read_auto_payload(token):
    data = read_json_file(auto_json_path(token), {})
    return data if isinstance(data, dict) else {}


def write_auto_payload(token, payload):
    data = payload if isinstance(payload, dict) else {}
    atomic_write_json(auto_json_path(token), data)
    return data
