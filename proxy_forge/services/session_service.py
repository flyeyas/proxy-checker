import threading
import time


class InMemorySessionStore:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self, session_id, total, **fields):
        session = {
            "results": [],
            "done": 0,
            "finished": False,
            "stop": None,
            "total": total,
            "created": time.time(),
        }
        session.update(fields)
        with self._lock:
            self._sessions[session_id] = session
        return session

    def create_stop_event(self, session_id):
        stop_event = threading.Event()
        with self._lock:
            session = self._sessions[session_id]
            session["stop"] = stop_event
        return stop_event

    def append_result(self, session_id, result):
        if not result:
            return
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session["results"].append(result)
                session["done"] += 1

    def finish(self, session_id):
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["finished"] = True
            snapshot = dict(session)
            snapshot["results"] = list(session.get("results", []))
            return snapshot

    def status_payload(self, session_id, since=0, max_concurrent_default=None):
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            all_results = list(session["results"])
            new_results = all_results[since:]
            return {
                "new": new_results,
                "total_done": session["done"],
                "total": session["total"],
                "finished": session["finished"],
                "target_profile": session.get("target_profile", "generic"),
                "max_concurrent": session.get("max_concurrent", max_concurrent_default),
                "valid_count": sum(1 for result in all_results if result.get("valid")),
                "unstable_count": sum(1 for result in all_results if result.get("unstable")),
                "invalid_count": sum(1 for result in all_results if not result.get("valid") and not result.get("unstable")),
                "cf_bypass_count": sum(1 for result in all_results if result.get("cf_bypass")),
            }

    def stop(self, session_id):
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.get("stop"):
                session["stop"].set()
                return True
        return False

    def cleanup_finished(self, max_age_seconds):
        now = time.time()
        with self._lock:
            expired_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.get("finished") and now - session.get("created", now) > max_age_seconds
            ]
            for session_id in expired_ids:
                del self._sessions[session_id]
            return len(expired_ids), len(self._sessions)
