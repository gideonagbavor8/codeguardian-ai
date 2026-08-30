"""
tests/test_github_scan.py
Tests for the GitHub repository scan source: URL/branch validation, safe
archive extraction, dependency discovery, the pipeline's GitHub branch
(including temp-dir cleanup), and the POST /scans/github endpoint.

No network access is required — archive downloads are stubbed.
"""
from __future__ import annotations

import io
import os
import uuid
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.finding import SecurityFinding
from app.models.report import Report
from app.models.scan import Scan, ScanStatus, SourceType
from app.services.ai.prompts import AIAnalysis
from app.services.scanner.base import RawSecurityFinding
from app.services.scanner.repo_fetcher import (
    FetchedRepo,
    RepoFetchError,
    _safe_extract,
    cleanup_repo,
    read_dependency_file,
    validate_branch,
    validate_github_url,
)
from app.tasks.scan_pipeline import run_scan_pipeline


# ─────────────────────────────────────────────────────────────
# 1. URL validation
# ─────────────────────────────────────────────────────────────

class TestValidateGithubUrl:
    @pytest.mark.parametrize("url,expected", [
        ("https://github.com/psf/requests", ("psf", "requests")),
        ("https://github.com/psf/requests/", ("psf", "requests")),
        ("https://github.com/psf/requests.git", ("psf", "requests")),
        ("https://www.github.com/psf/requests", ("psf", "requests")),
        ("https://github.com/psf/requests?tab=readme", ("psf", "requests")),
        ("  https://github.com/psf/requests  ", ("psf", "requests")),
        ("https://github.com/my-org/my.repo_v2", ("my-org", "my.repo_v2")),
    ])
    def test_accepts_public_repo_urls(self, url, expected):
        assert validate_github_url(url) == expected

    @pytest.mark.parametrize("url", [
        "http://github.com/psf/requests",            # not https
        "https://github.com.evil.example/psf/repo",  # lookalike host
        "https://evilgithub.com/psf/repo",
        "https://gitlab.com/psf/requests",
        "git@github.com:psf/requests.git",
        "https://user:pw@github.com/psf/requests",   # embedded credentials
        "https://github.com:8080/psf/requests",      # non-default port
        "https://github.com/psf",                    # missing repo
        "https://github.com/psf/requests/tree/main", # too many segments
        "https://github.com/../../etc/passwd",
        "https://github.com/psf/..",
        "file:///etc/passwd",
        "ftp://github.com/psf/requests",
        "",
        "   ",
    ])
    def test_rejects_everything_else(self, url):
        with pytest.raises(RepoFetchError):
            validate_github_url(url)

    def test_rejects_non_string(self):
        with pytest.raises(RepoFetchError):
            validate_github_url(None)  # type: ignore[arg-type]


class TestValidateBranch:
    @pytest.mark.parametrize("branch", ["main", "develop", "release/1.0", "v1.2.3", "a"])
    def test_accepts_plain_refs(self, branch):
        assert validate_branch(branch) == branch

    @pytest.mark.parametrize("branch", [
        "", "   ", "../evil", "..", "-x", "a//b", "b/",
        "main;rm -rf /", "$(whoami)", "main`id`", "main|ls", "a" * 300,
    ])
    def test_rejects_traversal_and_shell_metacharacters(self, branch):
        with pytest.raises(RepoFetchError):
            validate_branch(branch)


# ─────────────────────────────────────────────────────────────
# 2. Safe archive extraction
# ─────────────────────────────────────────────────────────────

def _write_zip(tmp_path, entries: dict[str, str], name: str = "a.zip") -> str:
    path = os.path.join(tmp_path, name)
    with zipfile.ZipFile(path, "w") as zf:
        for arcname, content in entries.items():
            zf.writestr(arcname, content)
    return path


class TestSafeExtract:
    def test_extracts_and_unwraps_github_top_level_dir(self, tmp_path):
        archive = _write_zip(str(tmp_path), {
            "repo-main/app.py": "import os\n",
            "repo-main/pkg/util.py": "x = 1\n",
        })
        root = _safe_extract(archive, os.path.join(str(tmp_path), "out"))

        assert os.path.basename(root) == "repo-main"
        assert os.path.isfile(os.path.join(root, "app.py"))
        assert os.path.isfile(os.path.join(root, "pkg", "util.py"))

    def test_rejects_parent_directory_traversal(self, tmp_path):
        archive = _write_zip(str(tmp_path), {"repo-main/../../evil.py": "pwned\n"})
        with pytest.raises(RepoFetchError, match="unsafe path"):
            _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_rejects_absolute_path_entry(self, tmp_path):
        archive = _write_zip(str(tmp_path), {"/etc/passwd": "root\n"})
        with pytest.raises(RepoFetchError):
            _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_rejects_windows_drive_path_entry(self, tmp_path):
        archive = _write_zip(str(tmp_path), {"C:/windows/evil.py": "x\n"})
        with pytest.raises(RepoFetchError):
            _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_skips_build_directories(self, tmp_path):
        archive = _write_zip(str(tmp_path), {
            "repo-main/app.py": "x = 1\n",
            "repo-main/node_modules/dep.js": "evil\n",
            "repo-main/.venv/lib.py": "x\n",
        })
        root = _safe_extract(archive, os.path.join(str(tmp_path), "out"))

        assert os.path.isfile(os.path.join(root, "app.py"))
        assert not os.path.exists(os.path.join(root, "node_modules"))
        assert not os.path.exists(os.path.join(root, ".venv"))

    def test_rejects_archive_over_size_limit(self, tmp_path):
        archive = _write_zip(str(tmp_path), {"repo-main/big.py": "A" * 200_000})
        with patch("app.services.scanner.repo_fetcher.settings") as s:
            s.MAX_REPO_SIZE_MB = 0            # 0 MB → everything is too big
            s.MAX_REPO_FILES = 100
            with pytest.raises(RepoFetchError, match="exceed"):
                _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_rejects_too_many_files(self, tmp_path):
        archive = _write_zip(
            str(tmp_path), {f"repo-main/f{i}.py": "x\n" for i in range(10)}
        )
        with patch("app.services.scanner.repo_fetcher.settings") as s:
            s.MAX_REPO_SIZE_MB = 50
            s.MAX_REPO_FILES = 3
            with pytest.raises(RepoFetchError, match="more than 3 files"):
                _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_rejects_empty_archive(self, tmp_path):
        archive = _write_zip(str(tmp_path), {})
        with pytest.raises(RepoFetchError, match="no scannable files"):
            _safe_extract(archive, os.path.join(str(tmp_path), "out"))

    def test_rejects_corrupt_archive(self, tmp_path):
        path = os.path.join(str(tmp_path), "bad.zip")
        with open(path, "wb") as fh:
            fh.write(b"not a zip file at all")
        with pytest.raises(RepoFetchError, match="not a valid zip"):
            _safe_extract(path, os.path.join(str(tmp_path), "out"))


# ─────────────────────────────────────────────────────────────
# 3. Dependency manifest discovery
# ─────────────────────────────────────────────────────────────

class TestReadDependencyFile:
    def test_finds_requirements_txt(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.25.0\n")
        content, ecosystem = read_dependency_file(str(tmp_path))
        assert "requests==2.25.0" in content
        assert ecosystem == "pip"

    def test_finds_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "x"}')
        content, ecosystem = read_dependency_file(str(tmp_path))
        assert ecosystem == "npm"
        assert "name" in content

    def test_prefers_shallowest_manifest(self, tmp_path):
        nested = tmp_path / "sub" / "deep"
        nested.mkdir(parents=True)
        (nested / "requirements.txt").write_text("deep==1.0\n")
        (tmp_path / "requirements.txt").write_text("shallow==1.0\n")
        content, _ = read_dependency_file(str(tmp_path))
        assert "shallow" in content

    def test_returns_empty_when_absent(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert read_dependency_file(str(tmp_path)) == ("", "pip")


class TestCleanupRepo:
    def test_removes_directory(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        (target / "f.py").write_text("x\n")
        cleanup_repo(str(target))
        assert not target.exists()

    def test_tolerates_none_and_missing(self, tmp_path):
        cleanup_repo(None)                                  # must not raise
        cleanup_repo(str(tmp_path / "does-not-exist"))      # must not raise


# ─────────────────────────────────────────────────────────────
# 4. Pipeline GitHub branch
# ─────────────────────────────────────────────────────────────

def _sec(severity: str = "HIGH") -> RawSecurityFinding:
    return RawSecurityFinding(
        tool="bandit", rule_id="B602", severity=severity, confidence="HIGH",
        file_path="src/app.py", line_number=9, code_snippet="shell=True",
        message="subprocess with shell=True", cwe_id="CWE-78",
    )


async def _make_github_scan(db, branch: str = "main") -> Scan:
    scan = Scan(
        user_id=uuid.uuid4(), name="gh", status=ScanStatus.PENDING.value,
        source_type=SourceType.GITHUB.value, language="python",
        source_meta={"repo_url": "https://github.com/owner/repo", "branch": branch},
    )
    db.add(scan)
    await db.commit()
    return scan


@pytest.mark.asyncio
async def test_pipeline_scans_repo_directory_and_cleans_up(db_session, tmp_path):
    """GitHub scans point the runners at the fetched directory, then delete it."""
    scan = await _make_github_scan(db_session)

    repo_dir = tmp_path / "codeguardian-repo-x"
    (repo_dir / "src").mkdir(parents=True)
    (repo_dir / "src" / "app.py").write_text("x = 1\n")
    fetched = FetchedRepo(
        temp_dir=str(repo_dir), root=str(repo_dir), owner="owner",
        repo="repo", ref="main",
    )

    with patch("app.tasks.scan_pipeline.fetch_repo",
               new_callable=AsyncMock, return_value=fetched), \
         patch("app.tasks.scan_pipeline.read_dependency_file",
               return_value=("requests==2.25.0", "pip")), \
         patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[_sec("HIGH")]) as mock_bandit, \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]) as mock_semgrep, \
         patch("app.tasks.scan_pipeline.audit_dependencies",
               new_callable=AsyncMock, return_value=[]) as mock_audit, \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="s", fix_suggestions=[], narrative="n")):

        await run_scan_pipeline(scan.id, db_session)

    # Runners received the repo directory, not a code string.
    assert mock_bandit.await_args.kwargs["target_path"] == str(repo_dir)
    assert mock_semgrep.await_args.kwargs["target_path"] == str(repo_dir)
    # The manifest discovered in the repo drove the dependency audit.
    mock_audit.assert_awaited_once_with("requests==2.25.0", "pip")

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.COMPLETE.value

    rows = (await db_session.execute(
        select(SecurityFinding).where(SecurityFinding.scan_id == scan.id)
    )).scalars().all()
    report = (await db_session.execute(
        select(Report).where(Report.scan_id == scan.id)
    )).scalar_one_or_none()

    assert len(rows) == 1 and rows[0].file_path == "src/app.py"
    assert report.total_security_issues == 1
    assert report.high_count == 1
    assert report.release_readiness_score == 90    # 100 - 10 (1 HIGH)

    # Temp dir removed on the success path.
    assert not repo_dir.exists()


@pytest.mark.asyncio
async def test_pipeline_cleans_up_when_scan_fails(db_session, tmp_path):
    """A scanner blowing up mid-scan must still delete the cloned repo."""
    scan = await _make_github_scan(db_session)

    repo_dir = tmp_path / "codeguardian-repo-fail"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("x = 1\n")
    fetched = FetchedRepo(
        temp_dir=str(repo_dir), root=str(repo_dir), owner="owner",
        repo="repo", ref="main",
    )

    with patch("app.tasks.scan_pipeline.fetch_repo",
               new_callable=AsyncMock, return_value=fetched), \
         patch("app.tasks.scan_pipeline.read_dependency_file", return_value=("", "pip")), \
         patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, side_effect=RuntimeError("bandit exploded")):

        await run_scan_pipeline(scan.id, db_session)

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.FAILED.value
    assert "bandit exploded" in (scan.error_message or "")
    assert not repo_dir.exists()


@pytest.mark.asyncio
async def test_pipeline_marks_failed_when_fetch_fails(db_session):
    """An unreachable repo fails the scan cleanly — no report, no findings."""
    scan = await _make_github_scan(db_session, branch="no-such-branch")

    with patch("app.tasks.scan_pipeline.fetch_repo", new_callable=AsyncMock,
               side_effect=RepoFetchError("Repository or branch not found")):
        await run_scan_pipeline(scan.id, db_session)

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.FAILED.value
    assert "not found" in (scan.error_message or "")

    report = (await db_session.execute(
        select(Report).where(Report.scan_id == scan.id)
    )).scalar_one_or_none()
    assert report is None


@pytest.mark.asyncio
async def test_pipeline_still_uses_code_string_for_snippet_scans(db_session):
    """Non-GitHub scans keep the existing single-blob behaviour (target_path=None)."""
    scan = Scan(
        user_id=uuid.uuid4(), name="snip", status=ScanStatus.PENDING.value,
        source_type=SourceType.SNIPPET.value, language="python",
        source_meta={"code": "import os", "language": "python"},
    )
    db_session.add(scan)
    await db_session.commit()

    with patch("app.tasks.scan_pipeline.fetch_repo", new_callable=AsyncMock) as mock_fetch, \
         patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[]) as mock_bandit, \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="", fix_suggestions=[], narrative="")):

        await run_scan_pipeline(scan.id, db_session)

    mock_fetch.assert_not_awaited()
    assert mock_bandit.await_args.kwargs["target_path"] is None
    assert mock_bandit.await_args.args[0] == "import os"


# ─────────────────────────────────────────────────────────────
# 5. POST /scans/github endpoint
# ─────────────────────────────────────────────────────────────

async def _token(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_github_endpoint_accepts_public_repo(client: AsyncClient):
    token = await _token(client, "gh-ok@example.com")

    with patch("app.routers.scans.asyncio.create_task"):
        resp = await client.post(
            "/api/v1/scans/github",
            json={
                "github_url": "https://github.com/psf/requests.git",
                "branch": "main",
                "project_name": "requests",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "scan_id" in body
    assert body["status"] == "PENDING"
    assert body["poll_url"].endswith("/status")


@pytest.mark.asyncio
async def test_github_endpoint_stores_normalised_url_and_source_type(
    client: AsyncClient, db_session
):
    token = await _token(client, "gh-meta@example.com")

    with patch("app.routers.scans.asyncio.create_task"):
        resp = await client.post(
            "/api/v1/scans/github",
            # trailing slash + .git must be normalised away before storage
            json={"github_url": "https://github.com/psf/requests.git/", "branch": "main"},
            headers={"Authorization": f"Bearer {token}"},
        )

    scan_id = uuid.UUID(resp.json()["scan_id"])
    scan = (await db_session.execute(
        select(Scan).where(Scan.id == scan_id)
    )).scalar_one()

    assert scan.source_type == SourceType.GITHUB.value
    assert scan.source_meta["repo_url"] == "https://github.com/psf/requests"
    assert scan.source_meta["branch"] == "main"
    assert scan.name == "psf/requests"        # default name from owner/repo


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"github_url": "http://github.com/psf/requests"},
    {"github_url": "https://gitlab.com/psf/requests"},
    {"github_url": "https://github.com.evil.example/psf/repo"},
    {"github_url": "git@github.com:psf/requests.git"},
    {"github_url": "https://github.com/psf"},
    {"github_url": "https://github.com/psf/requests", "branch": "../../etc"},
    {"github_url": "https://github.com/psf/requests", "branch": "main;rm -rf /"},
])
async def test_github_endpoint_rejects_unsafe_input_with_400(
    client: AsyncClient, payload
):
    token = await _token(client, f"gh-bad-{abs(hash(str(payload)))}@example.com")

    with patch("app.routers.scans.asyncio.create_task") as mock_task:
        resp = await client.post(
            "/api/v1/scans/github",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 400
    assert isinstance(resp.json()["detail"], str)
    mock_task.assert_not_called()      # no background scan was started


@pytest.mark.asyncio
async def test_github_endpoint_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/scans/github",
        json={"github_url": "https://github.com/psf/requests"},
    )
    assert resp.status_code == 401
