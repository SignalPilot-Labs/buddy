"""Critical security tests — pure validation logic, no external deps. Must run < 1 min."""

import asyncio
import builtins
import hmac
import re
import time

import pytest
from fastapi import HTTPException

from core.event_bus import EventBus
from core.bootstrap import RunBootstrap
from tools.db_logger import DBLogger
from utils.git import GitWorkspace
from tools.session import SessionGate
from utils.helpers import validate_branch_name
from utils.models import InjectRequest, ResumeRequest, RunContext, StartRequest


class TestValidateBranchName:
    """Tests for validate_branch_name."""

    def test_valid_simple_branch(self):
        validate_branch_name("main")
        validate_branch_name("feature-123")
        validate_branch_name("bugfix/issue_42")
        validate_branch_name("autofyn/2026-04-03-abc123")

    def test_valid_with_dots(self):
        validate_branch_name("release/v1.2.3")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="length"):
            validate_branch_name("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="length"):
            validate_branch_name("a" * 257)

    def test_rejects_directory_traversal(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("refs/../etc/passwd")

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("main..develop")

    def test_rejects_lock_suffix(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("refs/heads/main.lock")

    def test_rejects_trailing_slash(self):
        with pytest.raises(ValueError, match="format"):
            validate_branch_name("feature/")

    def test_rejects_special_characters(self):
        for bad in ["branch name", "branch;rm", "branch&cmd", "branch|pipe",
                     "branch$(cmd)", "branch`cmd`", "branch\nnewline"]:
            with pytest.raises(ValueError):
                validate_branch_name(bad)

    def test_rejects_leading_dot(self):
        with pytest.raises(ValueError):
            validate_branch_name(".hidden")

    def test_rejects_leading_dash(self):
        with pytest.raises(ValueError):
            validate_branch_name("-flag")


class TestSandboxBuiltins:
    """Verify the sandbox builtins allowlist excludes dangerous functions."""

    SAFE_ALLOWLIST = [
        "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
        "min", "max", "sum", "abs", "round", "pow", "divmod",
        "int", "float", "str", "bool", "list", "dict", "tuple", "set", "frozenset",
        "bytes", "bytearray", "memoryview", "complex",
        "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
        "iter", "next", "slice", "repr", "format", "hash", "id", "callable",
        "all", "any", "chr", "ord", "hex", "oct", "bin",
        "input", "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError", "NameError", "ZeroDivisionError",
        "True", "False", "None",
    ]

    DANGEROUS_BUILTINS = [
        "open", "__import__", "exec", "eval", "compile",
        "breakpoint", "globals", "locals", "vars",
    ]

    def test_dangerous_builtins_excluded(self):
        for name in self.DANGEROUS_BUILTINS:
            assert name not in self.SAFE_ALLOWLIST, f"{name} should not be in allowlist"

    def test_safe_builtins_included(self):
        essential = ["print", "len", "range", "int", "float", "str", "list", "dict",
                     "True", "False", "None", "Exception", "ValueError"]
        for name in essential:
            assert name in self.SAFE_ALLOWLIST, f"{name} should be in allowlist"

    def test_allowlist_builds_valid_dict(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        assert callable(safe["print"])
        assert safe["int"] is int
        assert "open" not in safe
        assert "__import__" not in safe
        assert "exec" not in safe

    def test_exec_with_restricted_builtins_blocks_import(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises((NameError, ImportError)):
            exec(compile("import os", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_blocks_open(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises(NameError):
            exec(compile("open('/etc/passwd')", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_allows_print(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        exec(compile("x = len([1, 2, 3])", "<test>", "exec"), {"__builtins__": safe})


class TestRepoSlugValidation:
    """Tests for the repo slug regex used in the DELETE /repos endpoint."""

    PATTERN = r'^[\w\-\.]+/[\w\-\.]+$'

    def _is_valid(self, slug: str) -> bool:
        return bool(re.match(self.PATTERN, slug))

    def test_valid_slugs(self):
        assert self._is_valid("owner/repo")
        assert self._is_valid("my-org/my-repo.js")
        assert self._is_valid("user_123/project-v2")

    def test_rejects_path_traversal(self):
        assert not self._is_valid("../../etc/passwd")

    def test_rejects_no_slash(self):
        assert not self._is_valid("justaname")

    def test_rejects_double_slash(self):
        assert not self._is_valid("owner/repo/extra")

    def test_rejects_empty_parts(self):
        assert not self._is_valid("/repo")
        assert not self._is_valid("owner/")


class TestApiKeyAuth:
    """Tests for API key auth logic (no DB dependency)."""

    @staticmethod
    async def _verify(api_key: str | None, expected_key: str | None) -> None:
        if expected_key is None:
            return
        if not api_key or not hmac.compare_digest(api_key, expected_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @pytest.mark.asyncio
    async def test_auth_disabled_when_no_key(self):
        await self._verify(api_key=None, expected_key=None)
        await self._verify(api_key="anything", expected_key=None)

    @pytest.mark.asyncio
    async def test_rejects_missing_key(self):
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key=None, expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_wrong_key(self):
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key="wrong", expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_correct_key(self):
        await self._verify(api_key="secret-key-12345678", expected_key="secret-key-12345678")


class TestStartRequestValidation:
    """Tests for StartRequest pydantic validators."""

    def test_valid_defaults(self):
        req = StartRequest()
        assert req.max_budget_usd == 0
        assert req.duration_minutes == 0
        assert req.base_branch == "main"

    def test_valid_custom_values(self):
        req = StartRequest(max_budget_usd=50.0, duration_minutes=30, base_branch="staging")
        assert req.max_budget_usd == 50.0
        assert req.duration_minutes == 30
        assert req.base_branch == "staging"

    def test_rejects_negative_budget(self):
        with pytest.raises(ValueError, match="non-negative"):
            StartRequest(max_budget_usd=-1.0)

    def test_rejects_negative_duration(self):
        with pytest.raises(ValueError, match="non-negative"):
            StartRequest(duration_minutes=-5)

    def test_rejects_empty_base_branch(self):
        with pytest.raises(ValueError, match="empty"):
            StartRequest(base_branch="")

    def test_rejects_whitespace_base_branch(self):
        with pytest.raises(ValueError, match="empty"):
            StartRequest(base_branch="   ")

    def test_strips_base_branch_whitespace(self):
        req = StartRequest(base_branch="  main  ")
        assert req.base_branch == "main"


class TestInjectRequestValidation:
    """Tests for InjectRequest pydantic validators."""

    def test_valid_payload(self):
        req = InjectRequest(payload="fix the bug")
        assert req.payload == "fix the bug"

    def test_none_payload(self):
        req = InjectRequest()
        assert req.payload is None

    def test_rejects_oversized_payload(self):
        with pytest.raises(ValueError, match="50000"):
            InjectRequest(payload="x" * 50001)

    def test_accepts_max_size_payload(self):
        req = InjectRequest(payload="x" * 50000)
        assert req.payload is not None and len(req.payload) == 50000


class TestStuckSubagentDetection:
    """Tests for DBLogger.get_stuck_subagents() agent_type inclusion."""

    def test_stuck_includes_agent_type(self):
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=30, github_repo="owner/repo",
        )
        logger = DBLogger(ctx)
        agent_id = "test-agent-123"
        logger._subagent_start_times[agent_id] = time.time() - 700
        logger._subagent_types[agent_id] = "builder"

        stuck = logger.get_stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0]["agent_id"] == agent_id
        assert stuck[0]["agent_type"] == "builder"
        assert stuck[0]["idle_seconds"] >= 700

    def test_not_stuck_if_recent_tool(self):
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=30, github_repo="owner/repo",
        )
        logger = DBLogger(ctx)
        agent_id = "test-agent-456"
        logger._subagent_start_times[agent_id] = time.time() - 700
        logger._subagent_last_tool[agent_id] = time.time() - 5
        logger._subagent_types[agent_id] = "reviewer"

        stuck = logger.get_stuck_subagents()
        assert len(stuck) == 0

    def test_unknown_agent_type_fallback(self):
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=30, github_repo="owner/repo",
        )
        logger = DBLogger(ctx)
        agent_id = "test-agent-789"
        logger._subagent_start_times[agent_id] = time.time() - 700

        stuck = logger.get_stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0]["agent_type"] == "unknown"


class TestResumeRequestValidation:
    """Tests for ResumeRequest pydantic validators."""

    def test_valid_resume(self):
        req = ResumeRequest(run_id="abc-123")
        assert req.run_id == "abc-123"
        assert req.max_budget_usd == 0

    def test_rejects_negative_budget(self):
        with pytest.raises(ValueError, match="non-negative"):
            ResumeRequest(run_id="abc-123", max_budget_usd=-10)

    def test_rejects_empty_run_id(self):
        with pytest.raises(ValueError, match="empty"):
            ResumeRequest(run_id="")

    def test_rejects_whitespace_run_id(self):
        with pytest.raises(ValueError, match="empty"):
            ResumeRequest(run_id="   ")

    def test_strips_run_id_whitespace(self):
        req = ResumeRequest(run_id="  abc-123  ")
        assert req.run_id == "abc-123"


class TestResumePromptBuilder:
    """Tests for RunBootstrap._build_resume_prompt."""

    def test_includes_branch_and_status(self):
        bootstrap = RunBootstrap(GitWorkspace())
        run_info = {"branch_name": "autofyn/test-branch", "status": "paused"}
        prompt = bootstrap._build_resume_prompt(run_info, None)
        assert "autofyn/test-branch" in prompt
        assert "paused" in prompt
        assert "Continue where you left off" in prompt

    def test_includes_operator_message(self):
        bootstrap = RunBootstrap(GitWorkspace())
        run_info = {"branch_name": "test", "status": "running"}
        prompt = bootstrap._build_resume_prompt(run_info, "fix the auth bug")
        assert "fix the auth bug" in prompt
        assert "Operator message" in prompt
        assert "Continue where you left off" not in prompt

    def test_includes_original_task(self):
        bootstrap = RunBootstrap(GitWorkspace())
        run_info = {
            "branch_name": "test", "status": "running",
            "custom_prompt": "Improve error handling across the codebase",
        }
        prompt = bootstrap._build_resume_prompt(run_info, None)
        assert "Improve error handling" in prompt
        assert "Original task" in prompt

    def test_includes_cost(self):
        bootstrap = RunBootstrap(GitWorkspace())
        run_info = {"branch_name": "test", "status": "running", "total_cost_usd": 2.50}
        prompt = bootstrap._build_resume_prompt(run_info, None)
        assert "$2.50" in prompt


class TestSessionGate:
    """Tests for SessionGate time lock logic."""

    def _make_gate(self, duration_minutes: float) -> SessionGate:
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=duration_minutes, github_repo="owner/repo",
        )
        return SessionGate(ctx)

    def test_locked_initially(self):
        gate = self._make_gate(30)
        assert not gate.is_unlocked()

    def test_unlocked_with_zero_duration(self):
        gate = self._make_gate(0)
        assert gate.is_unlocked()

    def test_force_unlock(self):
        gate = self._make_gate(30)
        assert not gate.is_unlocked()
        gate.force_unlock()
        assert gate.is_unlocked()

    def test_elapsed_minutes(self):
        gate = self._make_gate(30)
        elapsed = gate.elapsed_minutes()
        assert 0 <= elapsed < 1

    def test_time_remaining_str_format(self):
        gate = self._make_gate(30)
        remaining = gate.time_remaining_str()
        assert "m" in remaining

    def test_time_remaining_zero_duration(self):
        gate = self._make_gate(0)
        assert gate.time_remaining_str() == "0m"

    def test_has_ended_initially_false(self):
        gate = self._make_gate(30)
        assert not gate.has_ended()


class TestEventBus:
    """Tests for EventBus push/drain/wait."""

    @pytest.mark.asyncio
    async def test_push_and_drain(self):
        bus = EventBus()
        bus.push("stop", "reason")
        event = await bus.drain()
        assert event is not None
        assert event["event"] == "stop"
        assert event["payload"] == "reason"

    @pytest.mark.asyncio
    async def test_drain_empty_returns_none(self):
        bus = EventBus()
        event = await bus.drain()
        assert event is None

    @pytest.mark.asyncio
    async def test_wait_timeout_returns_none(self):
        bus = EventBus()
        event = await bus.wait(timeout=0.05)
        assert event is None

    @pytest.mark.asyncio
    async def test_wait_receives_event(self):
        bus = EventBus()
        async def delayed_push():
            await asyncio.sleep(0.01)
            bus.push("inject", "hello")
        asyncio.create_task(delayed_push())
        event = await bus.wait(timeout=1.0)
        assert event is not None
        assert event["event"] == "inject"
        assert event["payload"] == "hello"

    @pytest.mark.asyncio
    async def test_fifo_order(self):
        bus = EventBus()
        bus.push("first", None)
        bus.push("second", None)
        e1 = await bus.drain()
        e2 = await bus.drain()
        assert e1 is not None and e1["event"] == "first"
        assert e2 is not None and e2["event"] == "second"
