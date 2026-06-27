from proxy_forge.config import CONFIG_LOCAL_PATH
from proxy_forge.storage.files import atomic_write_json, read_json_file


def read_local_config():
    data = read_json_file(CONFIG_LOCAL_PATH, {})
    return data if isinstance(data, dict) else {}


def write_local_config(data):
    cleaned = data if isinstance(data, dict) else {}
    atomic_write_json(CONFIG_LOCAL_PATH, cleaned)
    return cleaned
