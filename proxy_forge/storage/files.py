import json
import os
import threading


def ensure_parent_dir(path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def atomic_write_json(path, data):
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp_path, path)


def atomic_write_text(path, text):
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp_path, path)


def read_json_file(path, fallback, logger=None):
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data is not None else fallback
    except Exception as exc:
        if logger:
            logger.warning("Failed to read json file", extra={"path": path, "error": str(exc)})
        return fallback
