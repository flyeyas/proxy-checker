import time
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


FIXED_TIMEZONES = {
    "Asia/Shanghai": 8,
    "Asia/Tokyo": 9,
    "Asia/Bangkok": 7,
    "Asia/Dubai": 4,
    "Europe/Berlin": 1,
    "Europe/London": 0,
    "America/New_York": -5,
    "America/Chicago": -6,
    "America/Denver": -7,
    "America/Los_Angeles": -8,
    "Australia/Sydney": 10,
}


def normalize_timezone(value, timezone_ids, default="UTC"):
    default_timezone = str(default or "UTC").strip() or "UTC"
    timezone_id = str(value or default_timezone).strip()
    return timezone_id if timezone_id in timezone_ids else "UTC"


def get_timezone(timezone_id, timezone_ids, default="UTC"):
    timezone_id = normalize_timezone(timezone_id, timezone_ids, default)
    if ZoneInfo is not None:
        try:
            return ZoneInfo(timezone_id)
        except Exception:
            pass
    if timezone_id in FIXED_TIMEZONES:
        return timezone(timedelta(hours=FIXED_TIMEZONES[timezone_id]))
    return timezone.utc


def format_timestamp(timestamp, timezone_id, timezone_ids, default="UTC"):
    if not timestamp:
        return None
    timezone_id = normalize_timezone(timezone_id, timezone_ids, default)
    dt = datetime.fromtimestamp(float(timestamp), get_timezone(timezone_id, timezone_ids, default))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def server_time_payload(timezone_id, timezone_ids, default="UTC"):
    now = time.time()
    timezone_id = normalize_timezone(timezone_id, timezone_ids, default)
    return {
        "timestamp": int(now),
        "text": format_timestamp(now, timezone_id, timezone_ids, default),
        "timezone": timezone_id,
        "server_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "server_timezone": time.strftime("%Z", time.localtime(now)),
    }
