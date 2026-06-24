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
