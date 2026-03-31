"""Base connector interface — every DB connector implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract base class for all database connectors."""

    @abstractmethod
    async def connect(self, connection_string: str) -> None:
        """Open connection pool."""

    @abstractmethod
    async def execute(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        """Execute query and return rows as list of dicts."""

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """Return schema info: tables with columns."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if connection is healthy."""

    @abstractmethod
    async def close(self) -> None:
        """Close connection pool."""
