import asyncio
import threading
import time

from proxy_checker.services.auto_run_service import (
    build_auto_log_entry,
    build_auto_runtime,
    build_auto_summary,
    build_failed_auto_runtime,
)
from proxy_checker.services.auto_scheduler_service import interrupt_auto_state, resolve_schedule_state
from proxy_checker.utils import normalize_proxy_list, sanitize_token


class AutoRunCoordinator:
    def __init__(
        self,
        *,
        runtime_store,
        record_service,
        fetch_service,
        check_engine_provider,
        normalize_config,
        compute_next_run,
        target_name,
        storage_factory,
        list_tokens,
        merge_repo_results,
        default_rounds,
        default_max_concurrent,
        default_timezone,
        logger=None,
    ):
        self.runtime_store = runtime_store
        self.record_service = record_service
        self.fetch_service = fetch_service
        self.check_engine_provider = check_engine_provider
        self.normalize_config = normalize_config
        self.compute_next_run = compute_next_run
        self.target_name = target_name
        self.storage_factory = storage_factory
        self.list_tokens = list_tokens
        self.merge_repo_results = merge_repo_results
        self.default_rounds = default_rounds
        self.default_max_concurrent = default_max_concurrent
        self.default_timezone = default_timezone
        self.logger = logger

    def get_status(self, token, since=0, client_session_id=""):
        token = sanitize_token(token)
        with self.runtime_store.locked():
            runtime = self.runtime_store.get(token)
            stopped = None if runtime else self.runtime_store.stopped_results(token)
            return self.record_service.status_payload(token, runtime, stopped, since, client_session_id)

    def is_running(self, token):
        return self.runtime_store.is_running(token)

    def update_runtime(self, token, **fields):
        token = sanitize_token(token)
        with self.runtime_store.locked():
            self.runtime_store.update(token, **fields)
            record = self.record_service.load(token)
            state = record["state"]
            if "stage" in fields:
                state["stage"] = fields["stage"]
            if "status" in fields:
                state["status"] = fields["status"]
            for key in ("total", "done", "source_count", "repo_count", "input_count", "skipped", "error"):
                if key in fields:
                    state[key] = fields[key]
            self.record_service.save(token, record)

    def build_summary(self, runtime, status, error=None, repo_summary=None):
        return build_auto_summary(
            runtime,
            status,
            default_rounds=self._setting(self.default_rounds),
            default_max_concurrent=self._setting(self.default_max_concurrent),
            default_timezone=self._setting(self.default_timezone),
            error=error,
            repo_summary=repo_summary,
        )

    def finalize_run(self, token, runtime, status, error=None, repo_summary=None):
        token = sanitize_token(token)
        summary = self.build_summary(runtime, status, error, repo_summary)
        with self.runtime_store.locked():
            record = self.record_service.load(token)
            config = self.normalize_config(record.get("config", {}))
            state = record["state"]
            state.update({
                "running": False,
                "status": status,
                "session_id": None,
                "stage": status,
                "finished_at": summary["finished_at"],
                "last_run_at": summary["finished_at"],
                "next_run_at": self.compute_next_run(config) if config.get("enabled") else None,
                "error": summary.get("error"),
            })
            self.record_service.append_history(state, summary)
            self.record_service.save(token, {"config": config, "state": state})
            if status == "stopped":
                self.runtime_store.remember_stopped_results(
                    token,
                    runtime.get("run_id"),
                    runtime.get("results", []),
                )
            else:
                self.runtime_store.clear_stopped_results(token)
            self.runtime_store.finish(token, runtime.get("run_id"))
        storage = self.storage_factory(token)
        storage.runs.update(runtime.get("log_id") or runtime.get("run_id"), {
            **summary,
            "type": "auto",
            "status": status,
            "session_id": runtime.get("run_id"),
            "target_name": self.target_name(summary.get("target_profile")),
        })
        if self.logger:
            self.logger.info("Auto run finished", extra={"token": token, "status": status, "summary": summary})

    def execute_run(self, token, config, run_id, reason):
        token = sanitize_token(token)
        runtime = None
        try:
            runtime = self.runtime_store.require(token)
            self.update_runtime(token, stage="fetching", status="running")
            if not self.fetch_service.available:
                raise RuntimeError("fetch_proxies 模块不可用")
            fetched, _source_name, err = self.fetch_service.fetch("all", 50000)
            if err:
                raise RuntimeError(err)
            source_proxies = normalize_proxy_list(fetched)

            self.update_runtime(token, stage="loading_repo", source_count=len(source_proxies))
            storage = self.storage_factory(token)
            repo = storage.repo.read()
            repo_proxies = normalize_proxy_list(item.get("proxy") for item in repo)
            combined = normalize_proxy_list(source_proxies + repo_proxies)

            if config["detect_mode"] == "skip":
                to_check = storage.checked.filter_unchecked(combined)
            else:
                to_check = combined
            skipped = len(combined) - len(to_check)
            self.runtime_store.update(
                token,
                target_profile=config["target_profile"],
                rounds=config["rounds"],
                max_concurrent=config["max_concurrent"],
                detect_mode=config["detect_mode"],
                repo_update_policy=config["repo_update_policy"],
                repo_count=len(repo),
                input_count=len(combined),
                total=len(to_check),
                skipped=skipped,
            )
            self.update_runtime(token, stage="detecting", repo_count=len(repo), total=len(to_check), skipped=skipped)

            if to_check:
                async def run_async():
                    await self.check_engine_provider().check_many_async(
                        proxies=to_check,
                        stop_event=runtime["stop"],
                        rounds=config["rounds"],
                        max_concurrent=config["max_concurrent"],
                        on_result=lambda result: self.publish_result(token, result),
                        target_profile=config["target_profile"],
                    )

                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(run_async())
                finally:
                    loop.close()

            if runtime["stop"].is_set():
                self.finalize_run(token, runtime, "stopped")
                return

            self.update_runtime(token, stage="updating_repo")
            detected = [result.get("original") or result.get("proxy") for result in runtime.get("results", [])]
            storage.checked.add(detected)
            repo_summary = self.merge_repo_results(
                token=token,
                repo=repo,
                results=runtime.get("results", []),
                checked_inputs=to_check,
                policy=config["repo_update_policy"],
            )
            self.finalize_run(token, runtime, "completed", repo_summary=repo_summary)
        except Exception as exc:
            if runtime is None:
                runtime = build_failed_auto_runtime(
                    run_id,
                    reason,
                    config,
                    default_rounds=self._setting(self.default_rounds),
                    default_max_concurrent=self._setting(self.default_max_concurrent),
                )
            if self.logger:
                self.logger.error("Auto run failed", extra={"token": token, "error": str(exc)}, exc_info=True)
            self.finalize_run(token, runtime, "failed", error=exc)

    def publish_result(self, token, result):
        self.runtime_store.append_result(token, result)

    def start_run(self, token, reason="schedule"):
        token = sanitize_token(token)
        with self.runtime_store.locked():
            if self.runtime_store.has(token):
                return False, "自动任务正在执行"
            record = self.record_service.load(token)
            config = self.normalize_config(record.get("config", {}))
            if reason == "schedule" and not config.get("enabled"):
                return False, "自动任务未启用"
            run_id = f"auto_{int(time.time())}_{id(config)}"
            started_at = time.time()
            target_name = self.target_name(config["target_profile"])
            storage = self.storage_factory(token)
            log_id = storage.runs.insert(build_auto_log_entry(run_id, reason, started_at, config, target_name))
            runtime = build_auto_runtime(run_id, log_id, reason, started_at, config, threading.Event())
            self.runtime_store.create(token, runtime)
            state = record["state"]
            state.update({
                "running": True,
                "status": "running",
                "session_id": run_id,
                "stage": "starting",
                "started_at": int(runtime["started_at"]),
                "finished_at": None,
                "next_run_at": self.compute_next_run(config, runtime["started_at"]) if config.get("enabled") else None,
                "error": None,
            })
            self.record_service.save(token, {"config": config, "state": state})

        thread = threading.Thread(target=self.execute_run, args=(token, config, run_id, reason), daemon=True)
        self.runtime_store.set_thread(token, thread)
        thread.start()
        return True, run_id

    def stop_run(self, token):
        token = sanitize_token(token)
        with self.runtime_store.locked():
            runtime = self.runtime_store.stop(token)
            if not runtime:
                return False
            record = self.record_service.load(token)
            record["state"]["status"] = "stopping"
            record["state"]["stage"] = "stopping"
            self.record_service.save(token, record)
        return True

    def save_config(self, token, config):
        token = sanitize_token(token)
        with self.runtime_store.locked():
            record = self.record_service.load(token)
            normalized = self.normalize_config(config)
            state = record["state"]
            running = self.runtime_store.has(token)
            if normalized.get("enabled"):
                state["status"] = "running" if running else "idle"
                if not running:
                    state["next_run_at"] = self.compute_next_run(normalized)
            else:
                state["status"] = "disabled"
                state["next_run_at"] = None
            state["running"] = running
            state["stage"] = "running" if running else state["status"]
            return self.record_service.save(token, {"config": normalized, "state": state})

    def mark_interrupted_runs(self):
        now = int(time.time())
        for token in self.list_tokens():
            with self.runtime_store.locked():
                record = self.record_service.load(token)
                config = self.normalize_config(record.get("config", {}))
                state = record["state"]
                summary = interrupt_auto_state(
                    state,
                    config,
                    now,
                    default_rounds=self._setting(self.default_rounds),
                    default_max_concurrent=self._setting(self.default_max_concurrent),
                )
                if not summary:
                    continue
                self.record_service.append_history(state, summary)
                self.record_service.save(token, {"config": config, "state": state})

    def scheduler_loop(self):
        while True:
            due_tokens = []
            now = time.time()
            for token in self.list_tokens():
                with self.runtime_store.locked():
                    record = self.record_service.load(token)
                    config = self.normalize_config(record.get("config", {}))
                    state = record["state"]
                    due, changed = resolve_schedule_state(
                        config,
                        state,
                        self.runtime_store.has(token),
                        now,
                        self.compute_next_run,
                    )
                    if changed:
                        self.record_service.save(token, {"config": config, "state": state})
                        continue
                    if due:
                        due_tokens.append(token)
            for token in due_tokens:
                started, message = self.start_run(token, "schedule")
                if started:
                    if self.logger:
                        self.logger.info("Scheduled auto run started", extra={"token": token})
                elif self.logger:
                    self.logger.warning("Scheduled auto run skipped", extra={"token": token, "message": message})
            time.sleep(30)

    def start_scheduler(self):
        self.mark_interrupted_runs()
        threading.Thread(target=self.scheduler_loop, daemon=True).start()

    @staticmethod
    def _setting(value):
        return value() if callable(value) else value
