"""Tests for user activity timeline rendering and DB query.

Covers:
- _user_activity_block renders each action kind correctly
- get_user_activity returns initial task + control signals in order
- Empty activity produces no prompt section
- Pause/resume without inject renders correctly
- Resume with inject shows both entries
"""

from prompts.orchestrator import _user_activity_block
from utils.models import UserAction


class TestUserActivityBlockRendering:
    """_user_activity_block must render a chronological timeline."""

    def test_task_renders_with_quote(self) -> None:
        actions = [UserAction(timestamp="2026-04-13T12:00:00", kind="task", text="Fix auth")]
        block = _user_activity_block(actions)
        assert '## User activity (chronological)' in block
        assert '[2026-04-13 12:00:00] Task started: "Fix auth"' in block

    def test_message_renders_as_user_message(self) -> None:
        actions = [UserAction(timestamp="2026-04-13T12:15:00", kind="message", text="Focus on login")]
        block = _user_activity_block(actions)
        assert '[2026-04-13 12:15:00] User message: "Focus on login"' in block

    def test_pause_resume_render_plain(self) -> None:
        actions = [
            UserAction(timestamp="2026-04-13T12:30:00", kind="pause", text="Paused"),
            UserAction(timestamp="2026-04-13T12:35:00", kind="resume", text="Resumed"),
        ]
        block = _user_activity_block(actions)
        assert "[2026-04-13 12:30:00] Paused" in block
        assert "[2026-04-13 12:35:00] Resumed" in block

    def test_stop_renders_with_reason(self) -> None:
        actions = [UserAction(timestamp="2026-04-13T13:00:00", kind="stop", text="Stopped: Good enough")]
        block = _user_activity_block(actions)
        assert "[2026-04-13 13:00:00] Stopped: Good enough" in block

    def test_priority_message_appended(self) -> None:
        actions = [UserAction(timestamp="2026-04-13T12:00:00", kind="task", text="x")]
        block = _user_activity_block(actions)
        assert "The latest user message takes priority" in block

    def test_full_timeline_ordering(self) -> None:
        actions = [
            UserAction(timestamp="2026-04-13T12:00:00", kind="task", text="Migrate auth"),
            UserAction(timestamp="2026-04-13T12:15:00", kind="message", text="Skip token refresh"),
            UserAction(timestamp="2026-04-13T12:30:00", kind="pause", text="Paused"),
            UserAction(timestamp="2026-04-13T12:35:00", kind="resume", text="Resumed"),
            UserAction(timestamp="2026-04-13T12:35:01", kind="message", text="Just do login"),
            UserAction(timestamp="2026-04-13T13:00:00", kind="stop", text="Stopped: Done for now"),
        ]
        block = _user_activity_block(actions)
        lines = block.split("\n")
        # Header + 6 actions + priority message = 8 lines
        assert len(lines) == 8
        assert "Task started" in lines[1]
        assert "User message" in lines[2]
        assert "Paused" in lines[3]
        assert "Resumed" in lines[4]
        assert "Just do login" in lines[5]
        assert "Stopped" in lines[6]

    def test_resume_with_inject_shows_both(self) -> None:
        """When user resumes with a message, both resume and inject appear."""
        actions = [
            UserAction(timestamp="2026-04-13T12:35:00", kind="resume", text="Resumed"),
            UserAction(timestamp="2026-04-13T12:35:00", kind="message", text="Focus on auth"),
        ]
        block = _user_activity_block(actions)
        assert "Resumed" in block
        assert 'User message: "Focus on auth"' in block


class TestSignalRenderers:
    """The DB signal renderers must produce correct kind/text pairs."""

    def test_inject_produces_message_kind(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["inject"]("Fix the bug")
        assert kind == "message"
        assert text == "Fix the bug"

    def test_pause_produces_pause_kind(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["pause"](None)
        assert kind == "pause"
        assert text == "Paused"

    def test_resume_produces_resume_kind(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["resume"](None)
        assert kind == "resume"
        assert text == "Resumed"

    def test_stop_with_reason(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["stop"]("User requested")
        assert kind == "stop"
        assert text == "Stopped: User requested"

    def test_stop_without_reason(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["stop"](None)
        assert kind == "stop"
        assert text == "Stopped"

    def test_unlock_produces_unlock_kind(self) -> None:
        from utils.db import _SIGNAL_RENDERERS
        kind, text = _SIGNAL_RENDERERS["unlock"](None)
        assert kind == "unlock"
        assert text == "Time gate unlocked"
