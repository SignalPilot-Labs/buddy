"""Connector registry — maps DBType to connector class."""

from __future__ import annotations

from ..models import DBType
from .base import BaseConnector
from .postgres import PostgresConnector


_REGISTRY: dict[str, type[BaseConnector]] = {
    DBType.postgres: PostgresConnector,
}


def get_connector(db_type: DBType) -> BaseConnector:
    cls = _REGISTRY.get(db_type)
    if cls is None:
        raise ValueError(f"Unsupported database type: {db_type}. Supported: {list(_REGISTRY)}")
    return cls()
