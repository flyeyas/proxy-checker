import json
import os
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_LOCAL_PATH = os.path.join(BASE_DIR, "config.local.json")


def load_config():
    config = {}
    for name in ("config.json", "config.local.json"):
        path = os.path.join(BASE_DIR, name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            config.update(loaded)
    return config


CONFIG = load_config()


def get_config_value(key, env_name, default):
    if env_name in os.environ:
        return os.environ[env_name]
    return CONFIG.get(key, default)


def get_config_int(key, env_name, default):
    try:
        return int(get_config_value(key, env_name, default))
    except (TypeError, ValueError):
        return default


def get_config_bool(key, env_name, default):
    value = get_config_value(key, env_name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def runtime_path(name):
    return os.path.join(BASE_DIR, name)


def ensure_runtime_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


DATA_DIR = runtime_path("data")
LOG_DIR = runtime_path("logs")

REPO_DIR = DATA_DIR


def ensure_runtime_dirs():
    for path in (DATA_DIR, LOG_DIR):
        ensure_runtime_dir(path)


REPO_UPDATE_POLICIES = (
    "stable_only",
    "include_unstable",
    "archive_all",
    "grade_a_only",
    "grade_b_only",
    "grade_ab_only",
)

TIMEZONE_OPTIONS = (
    {"id": "UTC", "name": "UTC"},
    {"id": "Asia/Shanghai", "name": "中国/新加坡/马来西亚 UTC+8"},
    {"id": "Asia/Tokyo", "name": "日本/韩国 UTC+9"},
    {"id": "Asia/Bangkok", "name": "泰国/越南 UTC+7"},
    {"id": "Asia/Dubai", "name": "迪拜 UTC+4"},
    {"id": "Europe/London", "name": "伦敦"},
    {"id": "Europe/Berlin", "name": "欧洲中部"},
    {"id": "America/New_York", "name": "美国东部"},
    {"id": "America/Chicago", "name": "美国中部"},
    {"id": "America/Denver", "name": "美国山地"},
    {"id": "America/Los_Angeles", "name": "美国西部"},
    {"id": "Australia/Sydney", "name": "悉尼"},
)
TIMEZONE_IDS = {item["id"] for item in TIMEZONE_OPTIONS}

TIMEOUT = get_config_int("timeout", "TIMEOUT", 12)
DETECT_TIMEOUT = get_config_int("detect_timeout", "DETECT_TIMEOUT", 8)
MAX_CONCURRENT = get_config_int("max_concurrent", "MAX_CONCURRENT", 30)
MAX_CONCURRENT_LIMIT = get_config_int("max_concurrent_limit", "MAX_CONCURRENT_LIMIT", 200)
CHECK_ROUNDS = get_config_int("check_rounds", "CHECK_ROUNDS", 2)
MAX_CHECK_ROUNDS = get_config_int("max_check_rounds", "MAX_CHECK_ROUNDS", 3)
LOG_LIMIT = get_config_int("log_limit", "LOG_LIMIT", 100)
PORT = get_config_int("port", "PORT", 8888)
HTTP_THREADS = get_config_int("http_threads", "HTTP_THREADS", 16)

LOG_MAX_BYTES = get_config_int("log_max_bytes", "LOG_MAX_BYTES", 10 * 1024 * 1024)
LOG_BACKUP_COUNT = get_config_int("log_backup_count", "LOG_BACKUP_COUNT", 5)

PROXY_GATEWAY_ENABLED = get_config_bool("proxy_gateway_enabled", "PROXY_GATEWAY_ENABLED", True)
PROXY_GATEWAY_BIND = str(get_config_value("proxy_gateway_bind", "PROXY_GATEWAY_BIND", "127.0.0.1"))
PROXY_GATEWAY_PORT = get_config_int("proxy_gateway_port", "PROXY_GATEWAY_PORT", 7890)
PROXY_GATEWAY_TOKEN = str(get_config_value("proxy_gateway_token", "PROXY_GATEWAY_TOKEN", "")).strip()
PROXY_GATEWAY_GRADES = str(get_config_value("proxy_gateway_grades", "PROXY_GATEWAY_GRADES", "A,B"))
PROXY_GATEWAY_TIMEOUT = max(3, get_config_int("proxy_gateway_timeout", "PROXY_GATEWAY_TIMEOUT", 20))

AUTH_PASSWORD = str(get_config_value("auth_password", "AUTH_PASSWORD", "linux.do"))
AUTH_SESSION_DAYS = get_config_int("auth_session_days", "AUTH_SESSION_DAYS", 7)
AUTH_COOKIE_NAME = "proxy_forge_auth"
AUTH_SESSION_SECONDS = max(1, AUTH_SESSION_DAYS) * 86400
AUTH_SESSION_SECRET = str(get_config_value("auth_session_secret", "AUTH_SESSION_SECRET", AUTH_PASSWORD))

APP_TIMEZONE = str(get_config_value("timezone", "APP_TIMEZONE", "UTC"))
MAX_CHECK_ROUNDS = max(1, min(10, MAX_CHECK_ROUNDS))
CHECK_ROUNDS = max(1, min(MAX_CHECK_ROUNDS, CHECK_ROUNDS))
LOG_LIMIT = max(20, min(1000, LOG_LIMIT))
HTTP_THREADS = max(1, min(128, HTTP_THREADS))
if APP_TIMEZONE not in TIMEZONE_IDS:
    APP_TIMEZONE = "UTC"

LOG_FILE_PATH = str(get_config_value("log_file", "LOG_FILE", os.path.join(BASE_DIR, "server.log")))
if not os.path.isabs(LOG_FILE_PATH):
    LOG_FILE_PATH = os.path.join(BASE_DIR, LOG_FILE_PATH)


@dataclass
class Settings:
    base_dir: str
    repo_dir: str
    port: int
    http_threads: int
    timeout: int
    detect_timeout: int
    max_concurrent: int
    max_concurrent_limit: int
    check_rounds: int
    max_check_rounds: int
    log_limit: int
    app_timezone: str
    auth_password: str
    auth_session_days: int
    auth_session_seconds: int
    auth_session_secret: str
    proxy_gateway_enabled: bool
    proxy_gateway_bind: str
    proxy_gateway_port: int
    proxy_gateway_timeout: int

    @classmethod
    def load(cls):
        return cls(
            base_dir=BASE_DIR,
            repo_dir=REPO_DIR,
            port=PORT,
            http_threads=HTTP_THREADS,
            timeout=TIMEOUT,
            detect_timeout=DETECT_TIMEOUT,
            max_concurrent=MAX_CONCURRENT,
            max_concurrent_limit=MAX_CONCURRENT_LIMIT,
            check_rounds=CHECK_ROUNDS,
            max_check_rounds=MAX_CHECK_ROUNDS,
            log_limit=LOG_LIMIT,
            app_timezone=APP_TIMEZONE,
            auth_password=AUTH_PASSWORD,
            auth_session_days=AUTH_SESSION_DAYS,
            auth_session_seconds=AUTH_SESSION_SECONDS,
            auth_session_secret=AUTH_SESSION_SECRET,
            proxy_gateway_enabled=PROXY_GATEWAY_ENABLED,
            proxy_gateway_bind=PROXY_GATEWAY_BIND,
            proxy_gateway_port=PROXY_GATEWAY_PORT,
            proxy_gateway_timeout=PROXY_GATEWAY_TIMEOUT,
        )

    def settings_context(self):
        return {
            "timeout": self.timeout,
            "detect_timeout": self.detect_timeout,
            "max_concurrent": self.max_concurrent,
            "max_concurrent_limit": self.max_concurrent_limit,
            "check_rounds": self.check_rounds,
            "max_check_rounds": self.max_check_rounds,
            "log_limit": self.log_limit,
            "auth_password": self.auth_password,
            "auth_session_days": self.auth_session_days,
            "auth_session_seconds": self.auth_session_seconds,
            "auth_session_secret": self.auth_session_secret,
            "app_timezone": self.app_timezone,
        }

    def apply_resolved_settings(self, resolved):
        self.timeout = resolved["timeout"]
        self.detect_timeout = resolved["detect_timeout"]
        self.max_concurrent = resolved["max_concurrent"]
        self.max_concurrent_limit = resolved["max_concurrent_limit"]
        self.check_rounds = resolved["check_rounds"]
        self.max_check_rounds = resolved["max_check_rounds"]
        self.log_limit = resolved["log_limit"]
        self.auth_password = resolved["auth_password"]
        self.auth_session_days = resolved["auth_session_days"]
        self.auth_session_seconds = resolved["auth_session_seconds"]
        self.auth_session_secret = resolved["auth_session_secret"]
        self.app_timezone = resolved["app_timezone"]
