from dataclasses import dataclass

from proxy_checker.services.auto_coordinator_service import AutoRunCoordinator
from proxy_checker.services.auto_record_service import AutoRecordService
from proxy_checker.services.auto_run_service import count_results
from proxy_checker.services.auto_runtime_service import AutoRuntimeStore
from proxy_checker.services.auto_service import AutoControlService
from proxy_checker.storage.auto_store import list_auto_tokens
from proxy_checker.storage.checked_store import append_checked_list, read_checked_list
from proxy_checker.storage.log_store import finish_log, start_log
from proxy_checker.storage.repo_store import read_repo_data


@dataclass(frozen=True)
class RuntimeAutoServices:
    runtime_store: AutoRuntimeStore
    record_service: AutoRecordService
    coordinator_service: AutoRunCoordinator
    control_service: AutoControlService


def create_runtime_auto_services(
    *,
    state,
    runtime_options_service,
    fetch_service,
    check_engine_provider,
    repo_update_service,
    logger,
):
    runtime_store = AutoRuntimeStore()
    record_service = AutoRecordService(
        normalize_config=runtime_options_service.normalize_auto_config,
        default_state=runtime_options_service.default_auto_state,
        compute_next_run=runtime_options_service.compute_next_run,
        format_timestamp=runtime_options_service.format_timestamp,
        server_time_payload=runtime_options_service.server_time_payload,
        count_results=count_results,
    )
    coordinator_service = AutoRunCoordinator(
        runtime_store=runtime_store,
        record_service=record_service,
        fetch_service=fetch_service,
        check_engine_provider=check_engine_provider,
        normalize_config=runtime_options_service.normalize_auto_config,
        compute_next_run=runtime_options_service.compute_next_run,
        target_name=runtime_options_service.get_target_profile_name,
        read_repo=read_repo_data,
        read_checked=read_checked_list,
        append_checked=append_checked_list,
        merge_repo_results=repo_update_service.merge_repo_results,
        start_log=start_log,
        finish_log=finish_log,
        list_tokens=list_auto_tokens,
        default_rounds=lambda: state.check_rounds,
        default_max_concurrent=lambda: state.max_concurrent,
        default_timezone=lambda: state.app_timezone,
        logger=logger,
    )
    control_service = AutoControlService(
        get_status=coordinator_service.get_status,
        save_config=coordinator_service.save_config,
        start_run=coordinator_service.start_run,
        stop_run=coordinator_service.stop_run,
    )
    return RuntimeAutoServices(
        runtime_store=runtime_store,
        record_service=record_service,
        coordinator_service=coordinator_service,
        control_service=control_service,
    )
