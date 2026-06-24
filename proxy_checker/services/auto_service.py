from proxy_checker.utils import sanitize_token


class AutoControlService:
    def __init__(self, *, get_status, save_config, start_run, stop_run):
        self.get_status = get_status
        self.save_config = save_config
        self.start_run = start_run
        self.stop_run = stop_run

    def get_payload(self, data):
        token = sanitize_token(data.get("token", "default"))
        return self.get_status(token, data.get("since", 0), data.get("session_id", ""))

    def save_payload(self, data):
        token = sanitize_token(data.get("token", "default"))
        record = self.save_config(token, data.get("config", {}))
        response = self.get_status(token)
        response["saved"] = True
        response["config"] = record["config"]
        response["state"] = record["state"]
        return response

    def run_now_payload(self, data):
        token = sanitize_token(data.get("token", "default"))
        started, message = self.start_run(token, "manual")
        response = self.get_status(token)
        response["started"] = started
        if not started:
            response["error"] = message
        return response

    def stop_payload(self, data):
        token = sanitize_token(data.get("token", "default"))
        stopped = self.stop_run(token)
        response = self.get_status(token, data.get("since", 0), data.get("session_id", ""))
        response["stopped"] = stopped
        return response

    def status_payload(self, data):
        return self.get_payload(data)
