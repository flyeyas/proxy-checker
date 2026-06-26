import os

from proxy_checker.utils import sanitize_token


def token_file_path(directory, token, extension):
    extension = str(extension or "").lstrip(".")
    return os.path.join(directory, f"{sanitize_token(token)}.{extension}")


def list_token_files(directory, extension):
    extension = f".{str(extension or '').lstrip('.')}"
    if not os.path.isdir(directory):
        return []
    tokens = []
    for name in os.listdir(directory):
        base, ext = os.path.splitext(name)
        if ext == extension and base:
            tokens.append(sanitize_token(base))
    return sorted(tokens)


def tenant_dir_path(data_dir, token):
    return os.path.join(data_dir, sanitize_token(token))


def list_tenant_dirs(data_dir, marker_file):
    if not os.path.isdir(data_dir):
        return []
    tokens = []
    for name in os.listdir(data_dir):
        sub = os.path.join(data_dir, name)
        if not os.path.isdir(sub):
            continue
        if not os.path.isfile(os.path.join(sub, marker_file)):
            continue
        token = sanitize_token(name)
        if token:
            tokens.append(token)
    return sorted(tokens)
