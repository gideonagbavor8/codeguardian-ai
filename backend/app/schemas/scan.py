"""
app/schemas/scan.py
Pydantic v2 schemas for scan endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────

class SnippetScanRequest(BaseModel):
    code: str = Field(min_length=1, description="Source code to scan")
    language: str = Field(default="python", max_length=50)
    name: str | None = Field(default=None, max_length=255)


class UploadScanMeta(BaseModel):
    """Optional metadata submitted alongside a file upload."""
    name: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=50)


# ── Responses ─────────────────────────────────────────────────

class ScanCreatedResponse(BaseModel):
    """Returned immediately (202) after a scan is accepted."""
    scan_id: uuid.UUID
    status: str
    poll_url: str


class ScanStatusResponse(BaseModel):
    """Lightweight polling payload."""
    scan_id: uuid.UUID
    status: str
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ScanResponse(BaseModel):
    """Full scan record."""
    id: uuid.UUID
    name: str | None
    status: str
    source_type: str
    language: str | None
    source_meta: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    total: int
    page: int
    limit: int
