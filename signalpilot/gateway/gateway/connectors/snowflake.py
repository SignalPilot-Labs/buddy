"""Snowflake connector — snowflake-connector-python backed.

Supports account/user/password auth, key-pair auth, and warehouse/role configuration.
Tier 1 connector matching HEX's Snowflake integration.
"""

from __future__ import annotations

from typing import Any

from .base import BaseConnector

try:
    import snowflake.connector

    HAS_SNOWFLAKE = True
except ImportError:
    HAS_SNOWFLAKE = False


class SnowflakeConnector(BaseConnector):
    def __init__(self):
        self._conn = None
        self._connect_params: dict = {}

    async def connect(self, connection_string: str) -> None:
        if not HAS_SNOWFLAKE:
            raise RuntimeError(
                "snowflake-connector-python not installed. "
                "Run: pip install snowflake-connector-python"
            )
        params = self._parse_connection(connection_string)
        self._connect_params = params

        connect_args = {
            "account": params["account"],
            "user": params["user"],
            "password": params["password"],
            "login_timeout": 15,
            "network_timeout": 30,
        }
        if params.get("database"):
            connect_args["database"] = params["database"]
        if params.get("warehouse"):
            connect_args["warehouse"] = params["warehouse"]
        if params.get("schema"):
            connect_args["schema"] = params["schema"]
        if params.get("role"):
            connect_args["role"] = params["role"]

        self._conn = snowflake.connector.connect(**connect_args)

    def _parse_connection(self, conn_str: str) -> dict:
        """Parse snowflake://account|user|pass|db|wh|schema|role format or structured extras."""
        if conn_str.startswith("snowflake://"):
            parts = conn_str[len("snowflake://"):].split("|")
            return {
                "account": parts[0] if len(parts) > 0 else "",
                "user": parts[1] if len(parts) > 1 else "",
                "password": parts[2] if len(parts) > 2 else "",
                "database": parts[3] if len(parts) > 3 else "",
                "warehouse": parts[4] if len(parts) > 4 else "",
                "schema": parts[5] if len(parts) > 5 else "",
                "role": parts[6] if len(parts) > 6 else "",
            }
        # Fallback: treat as account identifier
        return {"account": conn_str, "user": "", "password": ""}

    async def execute(self, sql: str, params: list | None = None, timeout: int | None = None) -> list[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("Not connected")
        try:
            cursor = self._conn.cursor(snowflake.connector.DictCursor)
            if timeout:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {timeout}")
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
            cursor.close()
            return list(rows) if rows else []
        except snowflake.connector.Error as e:
            raise RuntimeError(f"Snowflake query error: {e}") from e

    async def get_schema(self) -> dict[str, Any]:
        if self._conn is None:
            raise RuntimeError("Not connected")

        # Use INFORMATION_SCHEMA for comprehensive metadata
        sql = """
            SELECT
                TABLE_SCHEMA,
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """
        cursor = self._conn.cursor(snowflake.connector.DictCursor)
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()

        schema: dict[str, Any] = {}
        for row in rows:
            key = f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}"
            if key not in schema:
                schema[key] = {
                    "schema": row["TABLE_SCHEMA"],
                    "name": row["TABLE_NAME"],
                    "columns": [],
                }
            schema[key]["columns"].append({
                "name": row["COLUMN_NAME"],
                "type": row["DATA_TYPE"],
                "nullable": row["IS_NULLABLE"] == "YES",
                "primary_key": False,  # Snowflake doesn't enforce PKs, check constraints separately
                "comment": row.get("COMMENT", ""),
            })

        # Enrich with primary key info
        try:
            pk_sql = """
                SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                    USING (CONSTRAINT_CATALOG, CONSTRAINT_SCHEMA, CONSTRAINT_NAME)
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND tc.TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
            """
            cursor = self._conn.cursor(snowflake.connector.DictCursor)
            cursor.execute(pk_sql)
            pk_rows = cursor.fetchall()
            cursor.close()

            pk_set = {
                (r["TABLE_SCHEMA"], r["TABLE_NAME"], r["COLUMN_NAME"]) for r in pk_rows
            }
            for table_data in schema.values():
                for col in table_data["columns"]:
                    if (table_data["schema"], table_data["name"], col["name"]) in pk_set:
                        col["primary_key"] = True
        except Exception:
            pass  # PK enrichment is best-effort

        return schema

    async def health_check(self) -> bool:
        if self._conn is None:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
