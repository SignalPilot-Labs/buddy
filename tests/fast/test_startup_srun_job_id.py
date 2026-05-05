"""Tests for srun job ID extraction and AF_BOUND/AF_READY handling in connector startup.

Verifies that:
  - _stream_events parses slurm job IDs from srun stdout
  - AF_BOUND is treated as a log event (not promoted to ready)
  - AF_READY with actual hostname terminates the generator
"""

from unittest.mock import MagicMock

import pytest

from cli.connector.startup import _stream_events


def _make_process(lines: list[str]) -> MagicMock:
    """Build a mock process whose stdout yields the given lines."""
    encoded = [f"{line}\n".encode() for line in lines]

    async def _aiter():
        for chunk in encoded:
            yield chunk

    proc = MagicMock()
    proc.stdout = _aiter()
    return proc


class TestSrunJobIdExtraction:
    """_stream_events extracts slurm job IDs from srun output."""

    @pytest.mark.asyncio
    async def test_srun_queued_line_emits_backend_id(self) -> None:
        """srun: job NNNN queued → queued event with backend_id."""
        proc = _make_process([
            "srun: job 13303020 queued and waiting for resources",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        queued = [e for e in events if e["event"] == "queued"]
        assert len(queued) == 1
        assert queued[0]["backend_id"] == "13303020"

    @pytest.mark.asyncio
    async def test_srun_allocated_line_emits_backend_id(self) -> None:
        """srun: job NNNN has been allocated → queued event with backend_id."""
        proc = _make_process([
            "srun: job 99999 has been allocated resources",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        queued = [e for e in events if e["event"] == "queued"]
        assert len(queued) == 1
        assert queued[0]["backend_id"] == "99999"

    @pytest.mark.asyncio
    async def test_only_first_srun_job_id_emitted(self) -> None:
        """Multiple srun lines should only emit one queued event."""
        proc = _make_process([
            "srun: job 111 queued and waiting for resources",
            "srun: job 111 has been allocated resources",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        queued = [e for e in events if e["event"] == "queued"]
        assert len(queued) == 1
        assert queued[0]["backend_id"] == "111"

    @pytest.mark.asyncio
    async def test_no_srun_line_no_queued_event(self) -> None:
        """Without srun output, no queued event is emitted."""
        proc = _make_process([
            "some other log line",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        queued = [e for e in events if e["event"] == "queued"]
        assert len(queued) == 0

    @pytest.mark.asyncio
    async def test_srun_job_id_before_ready_marker(self) -> None:
        """Job ID should be extracted even when AF_READY comes after."""
        proc = _make_process([
            "srun: job 42 queued and waiting for resources",
            "srun: job 42 has been allocated resources",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        queued = [e for e in events if e["event"] == "queued"]
        ready = [e for e in events if e["event"] == "ready"]
        assert len(queued) == 1
        assert queued[0]["backend_id"] == "42"
        assert len(ready) == 1

    @pytest.mark.asyncio
    async def test_log_events_still_emitted_alongside_queued(self) -> None:
        """Log events should still be emitted for srun lines."""
        proc = _make_process([
            "srun: job 555 queued and waiting for resources",
            'AF_READY {"host":"node1","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@host")]

        log_events = [e for e in events if e["event"] == "log"]
        assert len(log_events) == 1
        assert "srun: job 555" in log_events[0]["line"]


class TestAfBoundNotPromoted:
    """AF_BOUND must NOT be promoted to ready — wait for AF_READY."""

    @pytest.mark.asyncio
    async def test_af_bound_becomes_log_event(self) -> None:
        """AF_BOUND should be emitted as a log event, not ready."""
        proc = _make_process([
            'AF_BOUND {"port":8080}',
            'AF_READY {"host":"node3108","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@loginnode")]

        ready = [e for e in events if e["event"] == "ready"]
        assert len(ready) == 1
        assert ready[0]["host"] == "node3108"
        assert ready[0]["port"] == 8080

        # AF_BOUND should be a log, not ready
        log_events = [e for e in events if e["event"] == "log"]
        assert any("AF_BOUND" in e["line"] for e in log_events)

    @pytest.mark.asyncio
    async def test_tunnel_uses_compute_node_not_login_node(self) -> None:
        """The ready event must have the compute node hostname, not ssh_target."""
        proc = _make_process([
            "srun: job 123 queued and waiting for resources",
            "srun: job 123 has been allocated resources",
            'AF_BOUND {"port":8080}',
            'AF_READY {"host":"compute-7","port":8080}',
        ])
        events = [e async for e in _stream_events(proc, "user@loginnode")]

        ready = [e for e in events if e["event"] == "ready"]
        assert len(ready) == 1
        assert ready[0]["host"] == "compute-7"  # NOT "loginnode"
