import unittest

from proxy_forge.runtime_services import RuntimeServices, create_runtime_services


class RuntimeServicesTest(unittest.TestCase):
    def test_create_runtime_services_wires_core_runtime_services(self):
        services = create_runtime_services()

        self.assertIsInstance(services, RuntimeServices)
        self.assertIs(services.settings_payload_service.proxy_gateway_service, services.proxy_gateway_service)
        self.assertIs(services.runtime_settings_apply_service.auth_service, services.auth_service)
        self.assertIs(services.auto_coordinator_service.runtime_store, services.auto_runtime_store)
        self.assertIs(services.auto_control_service.get_status.__self__, services.auto_coordinator_service)
        self.assertIs(services.lifecycle_service.gateway_runtime_service, services.gateway_runtime_service)
        self.assertIs(services.http_service.manual_check_service, services.manual_check_service)
        self.assertIs(services.http_service.auto_control_service, services.auto_control_service)
        self.assertIs(services.check_engine, services.engine_ref.engine)


if __name__ == "__main__":
    unittest.main()
