class RuntimeLifecycleService:
    def __init__(
        self,
        *,
        state,
        session_cleanup_service,
        auto_coordinator_service,
        gateway_runtime_service,
        deep_check_service,
        logger,
    ):
        self.state = state
        self.session_cleanup_service = session_cleanup_service
        self.auto_coordinator_service = auto_coordinator_service
        self.gateway_runtime_service = gateway_runtime_service
        self.deep_check_service = deep_check_service
        self.logger = logger

    def start_background_services(self):
        self.session_cleanup_service.start()
        self.auto_coordinator_service.start_scheduler()
        self.gateway_runtime_service.start()
        self.logger.info(
            f"Deep check (nodriver): {'available' if self.deep_check_service.available else 'not installed'}"
        )
        self.logger.info(f"Concurrency: {self.state.max_concurrent} | Rounds: {self.state.check_rounds}")
        self.logger.info("Auto mode scheduler started")
