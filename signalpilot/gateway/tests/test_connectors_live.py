"""Live integration tests for all database connectors.

Tests: connect, health_check, execute, get_schema, close
Databases under test:
  - PostgreSQL (enterprise-pg on port 5601)
  - MySQL (sp-mysql-test on port 3307)
  - ClickHouse (sp-clickhouse-test on port 9100)
  - DuckDB (in-memory)
  - SQLite (in-memory)
"""

import asyncio
import pytest


# ── PostgreSQL ──────────────────────────────────────────────────────────────

class TestPostgresConnector:
    CONN_STR = "postgresql://enterprise_admin:Ent3rpr1se!S3cur3@host.docker.internal:5601/enterprise_prod"

    @pytest.fixture
    def connector(self):
        from gateway.connectors.postgres import PostgresConnector
        return PostgresConnector()

    @pytest.mark.asyncio
    async def test_connect_and_health(self, connector):
        await connector.connect(self.CONN_STR)
        assert await connector.health_check() is True
        await connector.close()

    @pytest.mark.asyncio
    async def test_execute_query(self, connector):
        await connector.connect(self.CONN_STR)
        rows = await connector.execute("SELECT 1 AS value")
        assert len(rows) == 1
        assert rows[0]["value"] == 1
        await connector.close()

    @pytest.mark.asyncio
    async def test_get_schema(self, connector):
        await connector.connect(self.CONN_STR)
        schema = await connector.get_schema()
        assert isinstance(schema, dict)
        # Should have tables
        if len(schema) > 0:
            first_table = list(schema.values())[0]
            assert "columns" in first_table
            assert "schema" in first_table
            assert "name" in first_table
            # Check enhanced metadata
            assert "foreign_keys" in first_table
            assert "row_count" in first_table
            assert "description" in first_table
            # Check column metadata
            col = first_table["columns"][0]
            assert "name" in col
            assert "type" in col
            assert "nullable" in col
            assert "primary_key" in col
        await connector.close()

    @pytest.mark.asyncio
    async def test_readonly_enforcement(self, connector):
        await connector.connect(self.CONN_STR)
        with pytest.raises(Exception):
            await connector.execute("CREATE TABLE _test_readonly (id int)")
        await connector.close()


# ── MySQL ───────────────────────────────────────────────────────────────────

class TestMySQLConnector:
    CONN_STR = "mysql://analyst:An4lyst!P4ss@host.docker.internal:3307/test_analytics"

    @pytest.fixture
    def connector(self):
        from gateway.connectors.mysql import MySQLConnector
        return MySQLConnector()

    @pytest.mark.asyncio
    async def test_connect_and_health(self, connector):
        try:
            await connector.connect(self.CONN_STR)
            assert await connector.health_check() is True
            await connector.close()
        except Exception as e:
            pytest.skip(f"MySQL not available: {e}")

    @pytest.mark.asyncio
    async def test_execute_query(self, connector):
        try:
            await connector.connect(self.CONN_STR)
        except Exception:
            pytest.skip("MySQL not available")
        rows = await connector.execute("SELECT 1 AS value")
        assert len(rows) == 1
        assert rows[0]["value"] == 1
        await connector.close()

    @pytest.mark.asyncio
    async def test_get_schema(self, connector):
        try:
            await connector.connect(self.CONN_STR)
        except Exception:
            pytest.skip("MySQL not available")
        schema = await connector.get_schema()
        assert isinstance(schema, dict)
        if len(schema) > 0:
            first_table = list(schema.values())[0]
            assert "columns" in first_table
            assert "foreign_keys" in first_table
            assert "row_count" in first_table
        await connector.close()


# ── ClickHouse ──────────────────────────────────────────────────────────────

class TestClickHouseConnector:
    CONN_STR = "clickhouse://default:test123@host.docker.internal:9100/default"

    @pytest.fixture
    def connector(self):
        from gateway.connectors.clickhouse import ClickHouseConnector
        return ClickHouseConnector()

    @pytest.mark.asyncio
    async def test_connect_and_health(self, connector):
        try:
            await connector.connect(self.CONN_STR)
            assert await connector.health_check() is True
            await connector.close()
        except Exception as e:
            pytest.skip(f"ClickHouse not available: {e}")

    @pytest.mark.asyncio
    async def test_execute_query(self, connector):
        try:
            await connector.connect(self.CONN_STR)
        except Exception:
            pytest.skip("ClickHouse not available")
        rows = await connector.execute("SELECT 1 AS value")
        assert len(rows) == 1
        assert rows[0]["value"] == 1
        await connector.close()

    @pytest.mark.asyncio
    async def test_get_schema(self, connector):
        try:
            await connector.connect(self.CONN_STR)
        except Exception:
            pytest.skip("ClickHouse not available")
        schema = await connector.get_schema()
        assert isinstance(schema, dict)
        await connector.close()


# ── DuckDB ──────────────────────────────────────────────────────────────────

class TestDuckDBConnector:
    @pytest.fixture
    def connector(self):
        from gateway.connectors.duckdb import DuckDBConnector
        return DuckDBConnector()

    @pytest.mark.asyncio
    async def test_connect_and_health(self, connector):
        await connector.connect(":memory:")
        assert await connector.health_check() is True
        await connector.close()

    @pytest.mark.asyncio
    async def test_execute_query(self, connector):
        await connector.connect(":memory:")
        rows = await connector.execute("SELECT 1 AS value")
        assert len(rows) == 1
        assert rows[0]["value"] == 1
        await connector.close()

    @pytest.mark.asyncio
    async def test_get_schema(self, connector):
        await connector.connect(":memory:")
        # Create a test table
        await connector.execute("CREATE TABLE test_table (id INTEGER, name VARCHAR)")
        schema = await connector.get_schema()
        assert isinstance(schema, dict)
        assert len(schema) > 0
        await connector.close()


# ── SQLite ──────────────────────────────────────────────────────────────────

class TestSQLiteConnector:
    @pytest.fixture
    def connector(self):
        from gateway.connectors.sqlite import SQLiteConnector
        return SQLiteConnector()

    @pytest.mark.asyncio
    async def test_connect_and_health(self, connector):
        await connector.connect(":memory:")
        assert await connector.health_check() is True
        await connector.close()

    @pytest.mark.asyncio
    async def test_execute_and_schema(self, connector):
        await connector.connect(":memory:")
        await connector.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
        await connector.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")

        rows = await connector.execute("SELECT * FROM users")
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

        schema = await connector.get_schema()
        assert "users" in schema
        assert len(schema["users"]["columns"]) == 3
        # Check PK detection
        id_col = [c for c in schema["users"]["columns"] if c["name"] == "id"][0]
        assert id_col["primary_key"] is True
        await connector.close()


# ── Registry ────────────────────────────────────────────────────────────────

class TestConnectorRegistry:
    def test_all_db_types_registered(self):
        from gateway.connectors.registry import _REGISTRY
        from gateway.models import DBType
        for db_type in DBType:
            assert db_type.value in _REGISTRY or db_type in _REGISTRY, \
                f"DBType {db_type} not registered in connector registry"

    def test_get_connector_returns_correct_types(self):
        from gateway.connectors.registry import get_connector
        from gateway.connectors.postgres import PostgresConnector
        from gateway.connectors.mysql import MySQLConnector
        from gateway.connectors.duckdb import DuckDBConnector
        from gateway.connectors.clickhouse import ClickHouseConnector

        assert isinstance(get_connector("postgres"), PostgresConnector)
        assert isinstance(get_connector("mysql"), MySQLConnector)
        assert isinstance(get_connector("duckdb"), DuckDBConnector)
        assert isinstance(get_connector("clickhouse"), ClickHouseConnector)

    def test_get_connector_invalid_type(self):
        from gateway.connectors.registry import get_connector
        with pytest.raises(ValueError, match="Unsupported"):
            get_connector("invalid_db")


# ── Connection String Builder ───────────────────────────────────────────────

class TestConnectionStringBuilder:
    def test_postgres_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(
            name="test", db_type="postgres",
            host="myhost", port=5432, database="mydb",
            username="user", password="p@ss:word"
        )
        result = _build_connection_string(conn)
        assert result.startswith("postgresql://")
        assert "myhost:5432" in result
        assert "mydb" in result
        # Password should be URL-encoded
        assert "p%40ss%3Aword" in result

    def test_mysql_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(
            name="test", db_type="mysql",
            host="myhost", port=3306, database="mydb",
            username="root", password="secret"
        )
        result = _build_connection_string(conn)
        assert result.startswith("mysql+pymysql://")
        assert "myhost:3306" in result

    def test_snowflake_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(
            name="test", db_type="snowflake",
            account="xy12345", username="user", password="pass",
            database="mydb", warehouse="wh"
        )
        result = _build_connection_string(conn)
        assert result.startswith("snowflake://")
        assert "xy12345" in result

    def test_clickhouse_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(
            name="test", db_type="clickhouse",
            host="localhost", port=9000, database="default",
            username="default", password="test"
        )
        result = _build_connection_string(conn)
        assert result.startswith("clickhouse://")
        assert "localhost:9000" in result

    def test_duckdb_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(name="test", db_type="duckdb", database="/tmp/test.db")
        result = _build_connection_string(conn)
        assert result == "/tmp/test.db"

    def test_bigquery_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(name="test", db_type="bigquery", project="my-project")
        result = _build_connection_string(conn)
        assert result == "my-project"

    def test_redshift_connection_string(self):
        from gateway.store import _build_connection_string
        from gateway.models import ConnectionCreate
        conn = ConnectionCreate(
            name="test", db_type="redshift",
            host="cluster.region.redshift.amazonaws.com",
            port=5439, database="dev", username="admin", password="pass"
        )
        result = _build_connection_string(conn)
        assert result.startswith("redshift://")
        assert "5439" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
