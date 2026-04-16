"""db._build_url must mask password in repr/str but preserve the real DSN."""

from __future__ import annotations

from sqlalchemy import URL

from db.connection import _build_url


SENTINEL_PG_PASSWORD = "SENTINEL_PG_PASSWORD_abc123"


def _cfg() -> dict[str, str | int]:
    return {
        "user": "autofyn",
        "password": SENTINEL_PG_PASSWORD,
        "host": "db.local",
        "port": 5432,
        "name": "autofyn_test",
    }


class TestDbConnectionUrl:
    """URL built by _build_url must hide password in repr/str but round-trip."""

    def test_build_url_returns_url_instance(self) -> None:
        url = _build_url(_cfg())
        assert isinstance(url, URL)

    def test_url_repr_does_not_contain_password(self) -> None:
        url = _build_url(_cfg())
        assert SENTINEL_PG_PASSWORD not in repr(url)

    def test_url_str_does_not_contain_password(self) -> None:
        url = _build_url(_cfg())
        assert SENTINEL_PG_PASSWORD not in str(url)

    def test_url_repr_masks_with_stars(self) -> None:
        """SQLAlchemy renders hidden password as '***'."""
        url = _build_url(_cfg())
        assert "***" in repr(url)

    def test_url_round_trip_preserves_real_password(self) -> None:
        """render_as_string(hide_password=False) yields the real DSN."""
        url = _build_url(_cfg())
        plain = url.render_as_string(hide_password=False)
        assert SENTINEL_PG_PASSWORD in plain
        assert plain == (
            f"postgresql+psycopg://autofyn:{SENTINEL_PG_PASSWORD}"
            f"@db.local:5432/autofyn_test"
        )

    def test_url_components_preserved(self) -> None:
        """Driver, username, host, port, db name must all match cfg."""
        url = _build_url(_cfg())
        assert url.drivername == "postgresql+psycopg"
        assert url.username == "autofyn"
        assert url.password == SENTINEL_PG_PASSWORD
        assert url.host == "db.local"
        assert url.port == 5432
        assert url.database == "autofyn_test"
