from proxy_checker.storage.tenant import create_tenant_storage_factory
from proxy_checker.utils import sanitize_token


class AutoRecordService:
    def __init__(
        self,
        *,
        normalize_config,
        default_state,
        compute_next_run,
        format_timestamp,
        server_time_payload,
        count_results,
        storage_factory=None,
    ):
        self.normalize_config = normalize_config
        self.default_state = default_state
        self.compute_next_run = compute_next_run
        self.format_timestamp = format_timestamp
        self.server_time_payload = server_time_payload
        self.count_results = count_results
        self.storage_factory = storage_factory or create_tenant_storage_factory()

    def load(self, token):
        token = sanitize_token(token)
        data = self.storage_factory(token).auto.read()
        config = self.normalize_config(data.get("config") if isinstance(data, dict) else {})
        state = self.default_state(config)
        if isinstance(data, dict) and isinstance(data.get("state"), dict):
            state.update(data["state"])
        self.trim_history(state)
        if not config.get("enabled"):
            state["status"] = "disabled"
            state["next_run_at"] = None
        elif state.get("next_run_at") is None and not state.get("running"):
            state["next_run_at"] = self.compute_next_run(config)
        return {"config": config, "state": state}

    def save(self, token, record):
        token = sanitize_token(token)
        config = self.normalize_config(record.get("config", {}))
        state = record.get("state") if isinstance(record.get("state"), dict) else self.default_state(config)
        self.trim_history(state)
        self.storage_factory(token).auto.write({"config": config, "state": state})
        return {"config": config, "state": state}

    def append_history(self, state, summary):
        history = state.get("history")
        if not isinstance(history, list):
            history = []
        history.append(summary)
        state["history"] = history[-20:]
        state["last_summary"] = summary

    @staticmethod
    def trim_history(state):
        history = state.get("history")
        state["history"] = history[-20:] if isinstance(history, list) else []

    def status_payload(self, token, runtime=None, stopped=None, since=0, client_session_id=""):
        token = sanitize_token(token)
        record = self.load(token)
        config = self.normalize_config(record.get("config", {}))
        new_results = []
        results_index = 0

        if runtime:
            results = runtime.get("results", [])
            new_results, results_index = self.results_delta(results, since, client_session_id, runtime.get("run_id"))
            valid, unstable, invalid = self.count_results(results)
            record["state"].update({
                "running": True,
                "status": runtime.get("status", "running"),
                "session_id": runtime.get("run_id"),
                "stage": runtime.get("stage", "running"),
                "started_at": runtime.get("started_at"),
                "total": runtime.get("total", 0),
                "done": runtime.get("done", 0),
                "valid_count": valid,
                "unstable_count": unstable,
                "invalid_count": invalid,
                "source_count": runtime.get("source_count", 0),
                "repo_count": runtime.get("repo_count", 0),
                "input_count": runtime.get("input_count", 0),
                "skipped": runtime.get("skipped", 0),
                "error": runtime.get("error"),
            })
        elif stopped:
            results = stopped.get("results", [])
            new_results, results_index = self.results_delta(results, since, client_session_id, stopped.get("run_id"))

        state = record["state"]
        state["next_run_text"] = self.format_timestamp(state.get("next_run_at"), config.get("timezone"))
        state["started_text"] = self.format_timestamp(state.get("started_at"), config.get("timezone"))
        state["finished_text"] = self.format_timestamp(state.get("finished_at"), config.get("timezone"))
        record["config"] = config
        record["server_time"] = self.server_time_payload(config.get("timezone"))
        record["auto_mode"] = True
        record["new"] = new_results
        record["results_index"] = results_index
        return record

    @staticmethod
    def results_delta(results, since, client_session_id, run_id):
        try:
            since = int(since)
        except (TypeError, ValueError):
            since = 0
        if client_session_id and client_session_id != run_id:
            since = 0
        since = max(0, min(len(results), since))
        return results[since:], len(results)
