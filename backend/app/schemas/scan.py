"""
app/schemas/scan.py
Pydantic v2 schemas for scan endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.finding import SecurityFindingOut, DependencyFindingOut
from app.schemas.report import ReportResponse

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────

class SnippetScanRequest(BaseModel):
    code: str = Field(min_length=1, description="Source code to scan")
    language: str = Field(default="python", max_length=50)
    name: str | None = Field(default=None, max_length=255)


class GithubScanRequest(BaseModel):
    """Scan a public GitHub repository. Field names match the frontend body."""
    github_url: str = Field(min_length=1, max_length=500,
                            description="Public GitHub repository URL")
    branch: str = Field(default="main", max_length=255)
    project_name: str | None = Field(default=None, max_length=255)
    language: str = Field(default="python", max_length=50)


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
    """Lightweight polling payload — field names match Scan model columns."""
    id: uuid.UUID          # model column is `id`, not `scan_id`
    status: str
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ScanResponse(BaseModel):
    """Full scan record with findings and report."""
    id: uuid.UUID
    name: str | None
    status: str
    source_type: str
    language: str | None
    source_meta: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None

    security_findings: list["SecurityFindingOut"] = []
    dependency_findings: list["DependencyFindingOut"] = []
    report: "ReportResponse | None" = None

    model_config = {"from_attributes": True}

class ScanDetailResponse(ScanResponse):
    """Full scan details including findings and report — inherits all typed fields from ScanResponse."""

class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    total: int
    page: int
    limit: int
