"""
tests/test_database_url.py
Managed-Postgres URLs (Render, Heroku, …) carry libpq-only query parameters
that asyncpg rejects at connect() time, producing a 500 on every DB-backed
request.  These tests pin the normalisation.
"""
from __future__ import annotations

import pytest

from app.database import normalise_db_url


def test_strips_sslmode_and_passes_it_as_asyncpg_ssl_arg():
    url, connect_args = normalise_db_url(
        "postgresql+asyncpg://u:p@host:5432/db?sslmode=require"
    )
    assert "sslmode" not in url
    assert connect_args == {"ssl": "require"}


def test_upgrades_bare_postgres_scheme_to_asyncpg():
    url, _ = normalise_db_url("postgres://u:p@host:5432/db")
    assert url.startswith("postgresql+asyncpg://")


def test_render_style_url_is_fully_normalised():
    url, connect_args = normalise_db_url(
        "postgres://u:p@dpg-abc.oregon-postgres.render.com/mydb?sslmode=require"
    )
    assert url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in url
    assert connect_args == {"ssl": "require"}


@pytest.mark.parametrize("param", [
    "sslrootcert=/x.crt", "sslcert=/c.crt", "sslkey=/k.key",
    "channel_binding=require", "target_session_attrs=read-write",
    "gssencmode=disable",
])
def test_strips_other_libpq_only_params(param):
    url, connect_args = normalise_db_url(
        f"postgresql+asyncpg://u:p@host/db?{param}"
    )
    assert param.split("=")[0] not in url
    assert "ssl" not in connect_args


def test_preserves_credentials_and_database():
    url, _ = normalise_db_url(
        "postgresql+asyncpg://user:s3cret@host:5432/mydb?sslmode=require"
    )
    assert "user:s3cret@host:5432/mydb" in url


def test_leaves_clean_url_untouched():
    raw = "postgresql+asyncpg://u:p@localhost:5432/codeguardian"
    url, connect_args = normalise_db_url(raw)
    assert url == raw
    assert connect_args == {}


def test_leaves_sqlite_untouched():
    raw = "sqlite+aiosqlite:///:memory:"
    url, connect_args = normalise_db_url(raw)
    assert url == raw
    assert connect_args == {}
