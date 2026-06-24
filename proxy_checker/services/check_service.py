import asyncio
import threading
import time

from proxy_checker.responses import error_response, ok_response
from proxy_checker.utils import sanitize_token


class ManualCheckService:
    def __init__(
        self,
        *,
        session_store,
        check_engine=None,
        check_engine_provider=None,
        normalize_rounds,
        normalize_target_profile,
        normalize_max_concurrent,
        target_name,
        is_auto_running,
        start_log,
        finish_log,
        count_results,
        app_timezone,
        default_rounds,
        default_max_concurrent,
        logger=None,
    ):
        self.session_store = session_store
        self.check_engine_provider = check_engine_provider or (lambda: check_engine)
        self.normalize_rounds = normalize_rounds
        self.normalize_target_profile = normalize_target_profile
        self.normalize_max_concurrent = normalize_max_concurrent
        self.target_name = target_name
        self.is_auto_running = is_auto_running
        self.start_log = start_log
        self.finish_log = finish_log
        self.count_results = count_results
        self.app_timezone = app_timezone
        self.default_rounds = default_rounds
        self.default_max_concurrent = default_max_concurrent
        self.logger = logger

    def start_payload(self, body):
        proxies = body.get("proxies", [])
        rounds = self.normalize_rounds(body.get("rounds", self._setting(self.default_rounds)))
        target_profile = self.normalize_target_profile(body.get("target_profile", "generic"))
        max_concurrent = self.normalize_max_concurrent(body.get("max_concurrent", self._setting(self.default_max_concurrent)))
        token = sanitize_token(body.get("token", ""))
        if body.get("token") and self.is_auto_running(token):
            return error_response("自动任务正在执行，请先停止自动任务", auto_running=True)

        session_id = str(time.time()) + str(id(proxies))
        log_id = self.start_log(token, {
            "id": session_id,
            "type": "manual",
            "status": "running",
            "session_id": session_id,
            "started_at": int(time.time()),
            "target_profile": target_profile,
            "target_name": self.target_name(target_profile),
            "rounds": rounds,
            "max_concurrent": max_concurrent,
            "total": len(proxies),
            "timezone": self._setting(self.app_timezone),
        })
        self.session_store.create(
            session_id,
            total=len(proxies),
            rounds=rounds,
            target_profile=target_profile,
            max_concurrent=max_concurrent,
            token=token,
            log_id=log_id,
        )
        threading.Thread(target=self.run_check, args=(session_id, proxies, rounds, target_profile, max_concurrent, token), daemon=True).start()
        if self.logger:
            self.logger.info(f"Start check: session={session_id}, proxies={len(proxies)}, target_profile={target_profile}, max_concurrent={max_concurrent}")
        return {
            "session_id": session_id,
            "total": len(proxies),
            "rounds": rounds,
            "target_profile": target_profile,
            "max_concurrent": max_concurrent,
        }

    def status_payload(self, body):
        session_id = body.get("session_id", "")
        since = body.get("since", 0)
        return self.session_store.status_payload(
            session_id,
            since,
            self._setting(self.default_max_concurrent),
        ) or error_response("not found")

    def stop_payload(self, body):
        self.session_store.stop(body.get("session_id", ""))
        return ok_response()

    def run_check(self, session_id, proxies, rounds=None, target_profile=None, max_concurrent=None, token="default"):
        if rounds is None:
            rounds = self._setting(self.default_rounds)
        if max_concurrent is None:
            max_concurrent = self._setting(self.default_max_concurrent)
        rounds = self.normalize_rounds(rounds)
        target_profile = self.normalize_target_profile(target_profile)
        max_concurrent = self.normalize_max_concurrent(max_concurrent)
        token = sanitize_token(token)
        stop_event = self.session_store.create_stop_event(session_id)

        def publish_result(result):
            self.session_store.append_result(session_id, result)

        async def run_async():
            await self.check_engine_provider().check_many_async(
                proxies=proxies,
                stop_event=stop_event,
                rounds=rounds,
                max_concurrent=max_concurrent,
                on_result=publish_result,
                target_profile=target_profile,
            )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run_async())
        finally:
            loop.close()

        session = self.session_store.finish(session_id)
        if not session:
            return
        results = list(session.get("results", []))
        valid, unstable, invalid = self.count_results(results)
        status = "stopped" if stop_event.is_set() else "completed"
        self.finish_log(token, session.get("log_id") or session_id, {
            "type": "manual",
            "status": status,
            "session_id": session_id,
            "finished_at": int(time.time()),
            "target_profile": target_profile,
            "target_name": self.target_name(target_profile),
            "rounds": rounds,
            "max_concurrent": max_concurrent,
            "total": session.get("total", len(proxies)),
            "done": session.get("done", len(results)),
            "valid_count": valid,
            "unstable_count": unstable,
            "invalid_count": invalid,
        })

    @staticmethod
    def _setting(value):
        return value() if callable(value) else value
