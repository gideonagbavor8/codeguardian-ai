"""
tests/test_scans.py
Scan endpoint smoke tests (no live bandit/pip-audit needed).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_snippet_scan(client: AsyncClient):
    token = await _register_and_token(client, "scanner@example.com")

    # Mock the background pipeline so we don't need a real bandit install
    with patch("app.routers.scans.asyncio.create_task"):
        resp = await client.post(
            "/api/v1/scans/snippet",
            json={"code": "print('hello')", "language": "python", "name": "Test"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert "scan_id" in data
    assert data["status"] == "PENDING"
    assert "poll_url" in data


@pytest.mark.asyncio
async def test_list_scans_empty(client: AsyncClient):
    token = await _register_and_token(client, "listtest@example.com")
    resp = await client.get(
        "/api/v1/scans",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_scans_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/scans")
    assert resp.status_code == 401
