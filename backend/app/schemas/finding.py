"""
app/schemas/finding.py
Pydantic v2 schemas for security and dependency findings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel


class SecurityFindingOut(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    tool: str
    rule_id: str | None
    severity: str
    confidence: str | None
    file_path: str | None
    line_number: int | None
    code_snippet: str | None
    message: str
    cwe_id: str | None
    owasp_category: str | None
    created_at: datetime
    # Populated from the report's ai_fix_suggestions (injected at response time)
    ai_fix: str | None = None

    model_config = {"from_attributes": True}


class DependencyFindingOut(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    package_name: str
    installed_version: str | None
    fixed_version: str | None
    severity: str
    cve_ids: List[str] | None
    description: str | None
    ecosystem: str
    created_at: datetime

    model_config = {"from_attributes": True}
