"""Verify remote sandbox constants are properly defined and consistent."""

from db.constants import (
    ACTIVE_RUN_STATUSES,
    AUDIT_EVENT_TYPES,
    CONNECTOR_RECONNECT_TIMEOUT_SEC,
    RUN_STATUS_CONNECTOR_LOST,
    RUN_STATUSES,
    SANDBOX_BOOT_TIMEOUT_SEC,
    SANDBOX_HEARTBEAT_TIMEOUT_SEC,
    SANDBOX_QUEUE_TIMEOUT_SEC,
    SANDBOX_STOP_TIMEOUT_SEC,
    SANDBOX_TYPE_DOCKER,
    SANDBOX_TYPE_SLURM,
    SSH_CONNECT_TIMEOUT_SEC,
    VALID_SANDBOX_TYPES,
)


class TestRemoteSandboxConstants:
    """Remote sandbox constants are properly defined."""

    def test_connector_lost_in_run_statuses(self) -> None:
        assert RUN_STATUS_CONNECTOR_LOST in RUN_STATUSES

    def test_connector_lost_in_active_statuses(self) -> None:
        assert RUN_STATUS_CONNECTOR_LOST in ACTIVE_RUN_STATUSES

    def test_new_audit_event_types(self) -> None:
        assert "sandbox_queued" in AUDIT_EVENT_TYPES
        assert "startup_log" in AUDIT_EVENT_TYPES
        assert "sandbox_start_failed" in AUDIT_EVENT_TYPES

    def test_sandbox_types(self) -> None:
        assert SANDBOX_TYPE_SLURM == "slurm"
        assert SANDBOX_TYPE_DOCKER == "docker"
        assert VALID_SANDBOX_TYPES == frozenset({"slurm", "docker"})

    def test_timeout_constants_positive(self) -> None:
        assert SSH_CONNECT_TIMEOUT_SEC > 0
        assert SANDBOX_QUEUE_TIMEOUT_SEC > 0
        assert SANDBOX_BOOT_TIMEOUT_SEC > 0
        assert SANDBOX_STOP_TIMEOUT_SEC > 0
        assert CONNECTOR_RECONNECT_TIMEOUT_SEC > 0
        assert SANDBOX_HEARTBEAT_TIMEOUT_SEC > 0
