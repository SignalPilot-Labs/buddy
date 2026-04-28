"""SQLAlchemy ORM models — single source of truth for all database tables."""

import uuid
from datetime import datetime, timezone

from db.constants import RUN_STATUS_RUNNING, VALID_CONTROL_SIGNALS
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


def _utcnow() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Run(Base):
    """An agent improvement run."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    branch_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=RUN_STATUS_RUNNING)
    pr_url: Mapped[str | None] = mapped_column(String)
    total_tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_info: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    sdk_session_id: Mapped[str | None] = mapped_column(String)
    custom_prompt: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[float] = mapped_column(Float, default=0)
    base_branch: Mapped[str] = mapped_column(String, default="main")
    rate_limit_resets_at: Mapped[int | None] = mapped_column(Integer)
    diff_stats: Mapped[list | None] = mapped_column(JSONB)
    github_repo: Mapped[str | None] = mapped_column(String)
    context_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)

    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    control_signals: Mapped[list["ControlSignal"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ToolCall(Base):
    """A logged tool call from an agent run."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        CheckConstraint("phase IN ('pre', 'post')", name="ck_tool_calls_phase"),
        Index("ix_tool_calls_run_id", "run_id"),
        Index("ix_tool_calls_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    phase: Mapped[str] = mapped_column(String, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    permitted: Mapped[bool] = mapped_column(Boolean, default=True)
    deny_reason: Mapped[str | None] = mapped_column(String)
    agent_role: Mapped[str] = mapped_column(String, default="worker")
    tool_use_id: Mapped[str | None] = mapped_column(String)
    session_id: Mapped[str | None] = mapped_column(String)
    agent_id: Mapped[str | None] = mapped_column(String)

    run: Mapped["Run"] = relationship(back_populates="tool_calls")


class AuditLog(Base):
    """An audit event from an agent run."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_run_id", "run_id"),
        Index("ix_audit_log_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    run: Mapped["Run"] = relationship(back_populates="audit_logs")


class ControlSignal(Base):
    """A control signal sent from dashboard to agent."""

    __tablename__ = "control_signals"
    __table_args__ = (
        CheckConstraint(
            f"signal IN ({', '.join(repr(s) for s in VALID_CONTROL_SIGNALS)})",
            name="ck_control_signals_signal",
        ),
        Index("ix_control_signals_run_id", "run_id"),
        Index("ix_control_signals_pending", "run_id", "consumed"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    signal: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped["Run"] = relationship(back_populates="control_signals")


class Setting(Base):
    """Key-value settings with optional encryption."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow)
