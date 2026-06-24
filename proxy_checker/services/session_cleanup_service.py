import threading
import time


class SessionCleanupService:
    def __init__(self, session_store, *, max_age_seconds=600, interval_seconds=120, logger=None):
        self.session_store = session_store
        self.max_age_seconds = max_age_seconds
        self.interval_seconds = interval_seconds
        self.logger = logger

    def cleanup_once(self):
        removed, remaining = self.session_store.cleanup_finished(self.max_age_seconds)
        if removed and self.logger:
            self.logger.info(f"Cleaned up {removed} stale sessions, {remaining} remaining")
        return removed, remaining

    def loop(self):
        while True:
            time.sleep(self.interval_seconds)
            self.cleanup_once()

    def start(self):
        thread = threading.Thread(target=self.loop, daemon=True)
        thread.start()
        return thread
