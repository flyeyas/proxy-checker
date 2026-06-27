"""Auto-task backend.

Phase 1 implementation: wraps the existing auto_data/<token>.json storage
with an explicit path constructor. The on-disk shape (a dict containing
`config` and `state`) is unchanged.
"""

from proxy_forge.storage.files import atomic_write_json, read_json_file


class AutoBackend:
    def __init__(self, json_path):
        self._path = json_path

    def path(self):
        return self._path

    def read(self):
        data = read_json_file(self._path, {})
        return data if isinstance(data, dict) else {}

    def write(self, payload):
        data = payload if isinstance(payload, dict) else {}
        atomic_write_json(self._path, data)
        return data
