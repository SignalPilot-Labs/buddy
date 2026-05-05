"""Verify ForwardState dataclass."""

from cli.connector.forward_state import ForwardState


class TestForwardState:
    """ForwardState holds per-run tunnel state."""

    def test_log_buffer_max_size(self) -> None:
        state = ForwardState(
            run_key="test",
            ssh_target="user@host",
            sandbox_type="slurm",
            remote_host="compute-1",
            remote_port=9123,
            local_port=12345,
            tunnel_process=None,  # type: ignore[arg-type]
            start_process=None,
            sandbox_secret="secret",
            backend_id=None,
        )
        for i in range(200):
            state.log_buffer.append(f"line {i}")
        assert len(state.log_buffer) == 100
        assert state.log_buffer[0] == "line 100"
