from proxy_checker.services.auto_run_service import count_results
from proxy_checker.services.check_service import ManualCheckService
from proxy_checker.storage.log_store import finish_log, start_log


def create_manual_check_service(
    *,
    state,
    session_store,
    auto_runtime_store,
    check_engine_provider,
    runtime_options_service,
    logger,
):
    return ManualCheckService(
        session_store=session_store,
        check_engine_provider=check_engine_provider,
        normalize_rounds=runtime_options_service.normalize_rounds,
        normalize_target_profile=runtime_options_service.normalize_target_profile,
        normalize_max_concurrent=runtime_options_service.normalize_max_concurrent,
        target_name=runtime_options_service.get_target_profile_name,
        is_auto_running=lambda token: auto_runtime_store.is_running(token),
        start_log=start_log,
        finish_log=finish_log,
        count_results=count_results,
        app_timezone=lambda: state.app_timezone,
        default_rounds=lambda: state.check_rounds,
        default_max_concurrent=lambda: state.max_concurrent,
        logger=logger,
    )
