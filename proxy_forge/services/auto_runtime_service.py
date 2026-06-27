import threading
import time

from proxy_forge.utils import sanitize_token


class AutoRuntimeStore:
    def __init__(self):
        self._runtime = {}
        self._stopped_results = {}
        self._lock = threading.RLock()

    def locked(self):
        return self._lock

    def get(self, token):
        token = sanitize_token(token)
        with self._lock:
            return self._runtime.get(token)

    def require(self, token):
        token = sanitize_token(token)
        with self._lock:
            return self._runtime[token]

    def has(self, token):
        token = sanitize_token(token)
        with self._lock:
            return token in self._runtime

    def is_running(self, token):
        runtime = self.get(token)
        return bool(runtime and not runtime.get("finished"))

    def create(self, token, runtime):
        token = sanitize_token(token)
        with self._lock:
            if token in self._runtime:
                return False
            self._runtime[token] = runtime
            return True

    def update(self, token, **fields):
        token = sanitize_token(token)
        with self._lock:
            runtime = self._runtime.get(token)
            if runtime:
                runtime.update(fields)
            return runtime

    def set_thread(self, token, thread):
        return self.update(token, thread=thread)

    def append_result(self, token, result):
        if not result:
            return False
        token = sanitize_token(token)
        with self._lock:
            runtime = self._runtime.get(token)
            if not runtime:
                return False
            runtime["results"].append(result)
            runtime["done"] = runtime.get("done", 0) + 1
            return True

    def stop(self, token):
        token = sanitize_token(token)
        with self._lock:
            runtime = self._runtime.get(token)
            if not runtime:
                return None
            runtime["status"] = "stopping"
            runtime["stage"] = "stopping"
            stop_event = runtime.get("stop")
            if stop_event:
                stop_event.set()
            return runtime

    def finish(self, token, run_id):
        token = sanitize_token(token)
        with self._lock:
            runtime = self._runtime.get(token)
            if runtime and runtime.get("run_id") == run_id:
                runtime["finished"] = True
                del self._runtime[token]
                return True
            return False

    def remember_stopped_results(self, token, run_id, results, ttl_seconds=900):
        token = sanitize_token(token)
        with self._lock:
            self._stopped_results[token] = {
                "run_id": run_id,
                "results": list(results or []),
                "expires": time.time() + ttl_seconds,
            }

    def clear_stopped_results(self, token):
        token = sanitize_token(token)
        with self._lock:
            self._stopped_results.pop(token, None)

    def stopped_results(self, token):
        token = sanitize_token(token)
        with self._lock:
            stopped = self._stopped_results.get(token)
            if stopped and stopped.get("expires", 0) < time.time():
                del self._stopped_results[token]
                return None
            return stopped
