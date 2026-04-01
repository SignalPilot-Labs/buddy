"""Redshift connector — psycopg2-backed (wire-compatible with PostgreSQL).

Supports Amazon Redshift clusters and Redshift Serverless.
Uses the same PostgreSQL wire protocol but with Redshift-specific schema queries.
"""

from __future__ import annotations

from typing import Any

from .base import BaseConnector

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class RedshiftConnector(BaseConnector):
    def __init__(self):
        self._conn = None

    async def connect(self, connection_string: str) -> None:
        if not HAS_PSYCOPG2:
            raise RuntimeError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )
        # Normalize redshift:// to postgresql:// for psycopg2
        dsn = connection_string
        if dsn.startswith("redshift://"):
            dsn = "postgresql://" + dsn[len("redshift://"):]

        self._conn = psycopg2.connect(dsn, connect_timeout=15)
        self._conn.set_session(readonly=True, autocommit=True)

    async def execute(self, sql: str, params: list | None = None, timeout: int | None = None) -> list[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("Not connected")
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                if timeout:
                    cursor.execute(f"SET statement_timeout = {timeout * 1000}")
                cursor.execute(sql, params or ())
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
        except psycopg2.Error as e:
            # Reset the connection state after error
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise RuntimeError(f"Redshift query error: {e}") from e

    async def get_schema(self) -> dict[str, Any]:
        if self._conn is None:
            raise RuntimeError("Not connected")

        # Redshift uses SVV_COLUMNS for a comprehensive view across schemas
        sql = """
            SELECT
                schemaname AS table_schema,
                tablename AS table_name,
                "column" AS column_name,
                type AS data_type,
                CASE WHEN notnull THEN 'NO' ELSE 'YES' END AS is_nullable
            FROM pg_table_def
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
            ORDER BY schemaname, tablename, colnum
        """
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        schema: dict[str, Any] = {}
        for row in rows:
            key = f"{row['table_schema']}.{row['table_name']}"
            if key not in schema:
                schema[key] = {
                    "schema": row["table_schema"],
                    "name": row["table_name"],
                    "columns": [],
                }
            schema[key]["columns"].append({
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "primary_key": False,
            })

        # Enrich with primary keys from pg_constraint
        try:
            pk_sql = """
                SELECT
                    n.nspname AS table_schema,
                    cl.relname AS table_name,
                    a.attname AS column_name
                FROM pg_constraint con
                JOIN pg_class cl ON con.conrelid = cl.oid
                JOIN pg_namespace n ON cl.relnamespace = n.oid
                JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum = ANY(con.conkey)
                WHERE con.contype = 'p'
                    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            """
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(pk_sql)
                pk_rows = cursor.fetchall()

            pk_set = {
                (r["table_schema"], r["table_name"], r["column_name"]) for r in pk_rows
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
            with self._conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
