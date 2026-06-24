from proxy_checker.config import APP_TIMEZONE, TIMEZONE_OPTIONS
from proxy_checker.responses import ok_response
from proxy_checker.services.time_service import (
    format_timestamp,
    normalize_timezone,
    server_time_payload,
)
from proxy_checker.storage.log_store import clear_logs, read_logs


class LogService:
    def __init__(
        self,
        *,
        app_timezone=APP_TIMEZONE,
        timezone_options=TIMEZONE_OPTIONS,
        read_logs_func=read_logs,
        clear_logs_func=clear_logs,
    ):
        self.app_timezone = app_timezone
        self.timezone_ids = {item["id"] for item in timezone_options}
        self.read_logs = read_logs_func
        self.clear_logs = clear_logs_func

    def normalize_timezone(self, value):
        return normalize_timezone(value, self.timezone_ids, self.app_timezone)

    def format_timestamp(self, timestamp, timezone_id=None):
        return format_timestamp(
            timestamp,
            timezone_id or self.app_timezone,
            self.timezone_ids,
            self.app_timezone,
        )

    def server_time_payload(self, timezone_id=None):
        return server_time_payload(
            timezone_id or self.app_timezone,
            self.timezone_ids,
            self.app_timezone,
        )

    def payload(self, token):
        timezone_id = self.app_timezone
        logs = self.read_logs(token)
        for item in logs:
            timezone_id = self.normalize_timezone(item.get("timezone", self.app_timezone))
            item["started_text"] = self.format_timestamp(item.get("started_at"), timezone_id)
            item["finished_text"] = self.format_timestamp(item.get("finished_at"), timezone_id)
        return {
            "logs": logs,
            "count": len(logs),
            "server_time": self.server_time_payload(timezone_id),
        }

    def clear(self, token):
        self.clear_logs(token)
        return ok_response(**self.payload(token))
