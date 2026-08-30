"""
app/routers/scans.py
POST /scans/snippet  — scan pasted code
POST /scans/upload   — scan uploaded file
GET  /scans          — list user's scans
GET  /scans/{id}     — get single scan
GET  /scans/{id}/status — lightweight polling
DELETE /scans/{id}   — delete scan
"""
from __future__ import annotations

import asyncio
import io
import uuid
import zipfile
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.dependencies import CurrentUser, DBDep
from app.models.scan import Scan, ScanStatus, SourceType
from app.schemas.scan import (
    ScanCreatedResponse,
    ScanListResponse,
    ScanResponse,
    ScanStatusResponse,
    SnippetScanRequest,
    ScanDetailResponse,
)
from app.tasks.scan_pipeline import run_scan_pipeline

router = APIRouter(prefix="/scans", tags=["scans"])


# ── Helper ────────────────────────────────────────────────────

def _poll_url(scan_id: uuid.UUID) -> str:
    return f"/api/v1/scans/{scan_id}/status"


async def _fire_pipeline(scan_id: uuid.UUID) -> None:
    """Create a fresh DB session and run the pipeline as a background task."""
    async with AsyncSessionLocal() as session:
        await run_scan_pipeline(scan_id, session)


# ── Endpoints ─────────────────────────────────────────────────

@router.post(
    "/snippet",
    response_model=ScanCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit source code snippet for scanning",
)
async def create_snippet_scan(
    body: SnippetScanRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> ScanCreatedResponse:
    scan = Scan(
        user_id=current_user.id,
        name=body.name or f"Snippet scan",
        status=ScanStatus.PENDING.value,
        source_type=SourceType.SNIPPET.value,
        language=body.language,
        source_meta={
            "code": body.code,
            "language": body.language,
        },
    )
    db.add(scan)
    await db.flush()
    scan_id = scan.id
    await db.commit()

    asyncio.create_task(_fire_pipeline(scan_id))

    return ScanCreatedResponse(
        scan_id=scan_id,
        status=ScanStatus.PENDING.value,
        poll_url=_poll_url(scan_id),
    )


@router.post(
    "/upload",
    response_model=ScanCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a source file or requirements file for scanning",
)
async def create_upload_scan(
    current_user: CurrentUser,
    db: DBDep,
    file: UploadFile = File(...),
    name: Annotated[str | None, Form()] = None,
    language: Annotated[str, Form()] = "python",
    dep_file: Annotated[UploadFile | None, File()] = None,
    dep_ecosystem: Annotated[str, Form()] = "pip",
) -> ScanCreatedResponse:

    raw_bytes = await file.read()

    # ZIP project upload
    if file.filename and file.filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                source_parts: list[str] = []
                dependency_content = ""

                allowed_extensions = {
                    ".py", ".js", ".jsx", ".ts", ".tsx",
                    ".java", ".go", ".rb", ".php",
                    ".c", ".cpp", ".h", ".hpp",
                }

                for info in z.infolist():
                    if info.is_dir():
                        continue

                    filename = info.filename
                    lower_name = filename.lower()

                    # Ignore common generated/dependency directories
                    if any(
                        part in lower_name.split("/")
                        for part in [
                            "node_modules",
                            ".git",
                            "__pycache__",
                            ".venv",
                            "venv",
                            "dist",
                            "build",
                        ]
                    ):
                        continue

                    try:
                        content = z.read(info).decode(
                            "utf-8",
                            errors="replace",
                        )
                    except Exception:
                        continue

                    extension = ""
                    if "." in filename:
                        extension = "." + filename.rsplit(".", 1)[1].lower()

                    if extension in allowed_extensions:
                        source_parts.append(
                            f"\n# ===== FILE: {filename} =====\n{content}"
                        )

                    # Python dependencies
                    if lower_name.endswith("requirements.txt"):
                        dependency_content = content

                    # Node dependencies
                    elif lower_name.endswith("package.json"):
                        dependency_content = content
                        dep_ecosystem = "npm"

                code = "\n".join(source_parts)

                if not code.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No supported source-code files were found in the ZIP.",
                    )

                dep_content = dependency_content

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is not a valid ZIP archive.",
            )

    # Single source file upload
    else:
        code = raw_bytes.decode("utf-8", errors="replace")
        dep_content = ""

        if dep_file:
            dep_bytes = await dep_file.read()
            dep_content = dep_bytes.decode("utf-8", errors="replace")

    scan = Scan(
        user_id=current_user.id,
        name=name or file.filename or "Upload scan",
        status=ScanStatus.PENDING.value,
        source_type=SourceType.UPLOAD.value,
        language=language,
        source_meta={
            "code": code,
            "filename": file.filename,
            "language": language,
            "dep_file_content": dep_content,
            "dep_ecosystem": dep_ecosystem,
        },
    )

    db.add(scan)
    await db.flush()
    scan_id = scan.id
    await db.commit()

    asyncio.create_task(_fire_pipeline(scan_id))

    return ScanCreatedResponse(
        scan_id=scan_id,
        status=ScanStatus.PENDING.value,
        poll_url=_poll_url(scan_id),
    )


@router.get(
    "",
    response_model=ScanListResponse,
    summary="List all scans for the current user",
)
async def list_scans(
    current_user: CurrentUser,
    db: DBDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    scan_status: str | None = Query(default=None, alias="status"),
) -> ScanListResponse:
    base_query = select(Scan).where(Scan.user_id == current_user.id)
    if scan_status:
        base_query = base_query.where(Scan.status == scan_status.upper())

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated items
    items_result = await db.execute(
        base_query.order_by(Scan.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = items_result.scalars().all()

    return ScanListResponse(
        items=[ScanResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{scan_id}/status",
    response_model=ScanStatusResponse,
    summary="Lightweight status polling for a scan",
)
async def get_scan_status(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> ScanStatusResponse:
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == current_user.id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return ScanStatusResponse.model_validate(scan)


@router.get(
    "/{scan_id}",
    response_model=ScanDetailResponse,
    summary="Get full scan details",
)
async def get_scan_detail(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> ScanDetailResponse:
    result = await db.execute(
        select(Scan)
        .options(
            selectinload(Scan.security_findings),
            selectinload(Scan.dependency_findings),
            selectinload(Scan.report),
        )
        .where(Scan.id == scan_id, Scan.user_id == current_user.id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return ScanDetailResponse.model_validate(scan)


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a scan and all its findings",
)
async def delete_scan(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> Response:
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == current_user.id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    await db.delete(scan)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
