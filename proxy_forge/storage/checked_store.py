"""Legacy checked-list storage API.

Phase 2 thin wrapper: all functions delegate to ``TenantStorage(token).checked``.
"""

from proxy_forge.storage.tenant import TenantStorage

__all__ = [
    "checked_txt_path",
    "read_checked_list",
    "write_checked_list",
    "append_checked_list",
]


def checked_txt_path(token):
    return TenantStorage(token).checked.path()


def read_checked_list(token):
    return TenantStorage(token).checked.list()


def write_checked_list(token, proxies):
    return TenantStorage(token).checked.write(proxies)


def append_checked_list(token, proxies):
    return TenantStorage(token).checked.add(proxies)
