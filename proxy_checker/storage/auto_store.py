"""Legacy auto-task storage API.

Phase 2 thin wrapper: all functions delegate to ``TenantStorage(token).auto``.
"""

from proxy_checker.storage.tenant import TenantStorage, list_tenant_tokens

__all__ = [
    "auto_json_path",
    "list_auto_tokens",
    "read_auto_payload",
    "write_auto_payload",
]


def auto_json_path(token):
    return TenantStorage(token).auto.path()


def list_auto_tokens():
    return list_tenant_tokens()


def read_auto_payload(token):
    return TenantStorage(token).auto.read()


def write_auto_payload(token, payload):
    return TenantStorage(token).auto.write(payload)
