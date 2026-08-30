"""
app/services/scanner/repo_fetcher.py
Fetches a public GitHub repository into a temporary directory for scanning.

Security design:
- No subprocess is used.  The repository is downloaded as a zip archive over
  HTTPS, so there is no shell and no command-injection surface.
- The user-supplied URL is never used to make the request.  Only the owner and
  repo names are extracted from it, validated against a strict character set,
  and then a download URL is *constructed* against a fixed host.  A malicious
  URL therefore cannot redirect the fetch anywhere.
- Archive extraction rejects absolute paths, parent-directory traversal
  (zip-slip) and symlinks, and enforces caps on entry count and total
  inflated size (zip bombs).
- Only public github.com repositories are supported.  No credentials are ever
  sent, so a private repository simply 404s.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# github.com and codeload.github.com are the only hosts ever contacted.
_GITHUB_HOSTS = {"github.com", "www.github.com"}
_CODELOAD = "https://codeload.github.com"

# Owner / repo: must start alphanumeric and must not end with a dot, which
# rules out "", ".", ".." and any traversal attempt.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?$")

# Branch / tag refs.  Deliberately narrower than git's own rules.
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")

# Directories never worth scanning; skipped at extraction time so they cost
# nothing downstream.
_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".tox", ".eggs", ".next", "vendor",
}

_DEP_FILES = (
    ("requirements.txt", "pip"),
    ("package.json", "npm"),
)


class RepoFetchError(RuntimeError):
    """Raised for an invalid URL, an unreachable repo, or an unsafe archive."""


@dataclass
class FetchedRepo:
    """A downloaded repository on local disk."""
    temp_dir: str   # the directory to delete when finished
    root: str       # the directory to point scanners at
    owner: str
    repo: str
    ref: str

    @property
    def normalised_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


# ── Validation ────────────────────────────────────────────────

def validate_github_url(url: str) -> tuple[str, str]:
    """
    Parse *url* and return (owner, repo).

    Accepts only https://github.com/<owner>/<repo> (optionally with a
    trailing .git or /).  Raises RepoFetchError for anything else, including
    other hosts, other schemes, embedded credentials, non-default ports, and
    lookalike hosts such as github.com.evil.example.
    """
    if not isinstance(url, str) or not url.strip():
        raise RepoFetchError("Repository URL is required.")

    parsed = urlparse(url.strip())

    if parsed.scheme != "https":
        raise RepoFetchError("Repository URL must use https://.")

    # hostname is the bare host: lowercased, no userinfo, no port.
    if parsed.hostname not in _GITHUB_HOSTS:
        raise RepoFetchError("Only public github.com repository URLs are supported.")

    if parsed.username or parsed.password:
        raise RepoFetchError("Repository URL must not contain credentials.")

    if parsed.port is not None:
        raise RepoFetchError("Repository URL must not specify a port.")

    segments = [seg for seg in parsed.path.split("/") if seg]
    if len(segments) != 2:
        raise RepoFetchError(
            "Repository URL must be of the form https://github.com/owner/repo."
        )

    owner, repo = segments
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    for label, value in (("owner", owner), ("repository", repo)):
        if not _SEGMENT_RE.match(value):
            raise RepoFetchError(f"Invalid {label} name in repository URL.")

    return owner, repo


def validate_branch(branch: str) -> str:
    """Validate a branch/tag name and return it. Raises RepoFetchError."""
    branch = (branch or "").strip()
    if not branch:
        raise RepoFetchError("Branch name is required.")
    if ".." in branch or branch.endswith("/") or "//" in branch:
        raise RepoFetchError("Invalid branch name.")
    if not _BRANCH_RE.match(branch):
        raise RepoFetchError("Invalid branch name.")
    return branch


# ── Fetch ─────────────────────────────────────────────────────

async def fetch_repo(url: str, branch: str = "main") -> FetchedRepo:
    """
    Download *url* at *branch* into a fresh temporary directory.

    The caller owns the returned FetchedRepo.temp_dir and MUST delete it
    (see cleanup_repo) once scanning is done, including on failure.
    """
    owner, repo = validate_github_url(url)
    ref = validate_branch(branch)

    temp_dir = tempfile.mkdtemp(prefix="codeguardian-repo-")
    try:
        archive = await _download_archive(owner, repo, ref, temp_dir)
        root = _safe_extract(archive, os.path.join(temp_dir, "src"))
        try:
            os.unlink(archive)
        except OSError:
            pass
        return FetchedRepo(
            temp_dir=temp_dir, root=root, owner=owner, repo=repo, ref=ref
        )
    except Exception:
        # Never leak the temp dir if anything failed mid-fetch.
        cleanup_repo(temp_dir)
        raise


def cleanup_repo(temp_dir: str | None) -> None:
    """Remove a fetched repository's temporary directory. Never raises."""
    if not temp_dir:
        return
    shutil.rmtree(temp_dir, ignore_errors=True)


async def _download_archive(owner: str, repo: str, ref: str, dest_dir: str) -> str:
    """
    Stream the zip archive for owner/repo@ref to a file in *dest_dir*.
    The URL is constructed here — the caller's raw input is never used.
    """
    max_bytes = settings.MAX_REPO_SIZE_MB * 1024 * 1024
    archive_path = os.path.join(dest_dir, "repo.zip")

    # refs/heads/<ref> resolves branches; refs/tags/<ref> is the tag fallback.
    candidates = [
        f"{_CODELOAD}/{owner}/{repo}/zip/refs/heads/{ref}",
        f"{_CODELOAD}/{owner}/{repo}/zip/refs/tags/{ref}",
    ]

    last_status: int | None = None
    async with httpx.AsyncClient(
        timeout=settings.REPO_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        for candidate in candidates:
            try:
                async with client.stream("GET", candidate) as response:
                    if response.status_code == 404:
                        last_status = 404
                        continue
                    if response.status_code != 200:
                        last_status = response.status_code
                        continue

                    written = 0
                    with open(archive_path, "wb") as fh:
                        async for chunk in response.aiter_bytes(64 * 1024):
                            written += len(chunk)
                            if written > max_bytes:
                                raise RepoFetchError(
                                    f"Repository archive exceeds the "
                                    f"{settings.MAX_REPO_SIZE_MB} MB limit."
                                )
                            fh.write(chunk)
                    logger.info(
                        "Fetched %s/%s@%s (%d bytes)", owner, repo, ref, written
                    )
                    return archive_path
            except httpx.HTTPError as exc:
                raise RepoFetchError(f"Could not reach GitHub: {exc}") from exc

    if last_status == 404:
        raise RepoFetchError(
            f"Repository or branch not found: {owner}/{repo}@{ref}. "
            "Only public repositories are supported."
        )
    raise RepoFetchError(
        f"GitHub returned HTTP {last_status} for {owner}/{repo}@{ref}."
    )


# ── Safe extraction ───────────────────────────────────────────

def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _safe_extract(archive_path: str, dest_dir: str) -> str:
    """
    Extract *archive_path* into *dest_dir*, rejecting unsafe entries.
    Returns the directory scanners should be pointed at — GitHub wraps the
    tree in a single "<repo>-<ref>/" folder, which is unwrapped here.
    """
    os.makedirs(dest_dir, exist_ok=True)
    dest_root = os.path.realpath(dest_dir)

    max_bytes = settings.MAX_REPO_SIZE_MB * 1024 * 1024
    max_files = settings.MAX_REPO_FILES
    total_written = 0
    file_count = 0

    try:
        zf = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise RepoFetchError("Downloaded archive is not a valid zip file.") from exc

    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if _is_symlink(info):
                logger.debug("skipping symlink in archive: %s", info.filename)
                continue

            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise RepoFetchError("Archive contains an unsafe path entry.")
            if os.path.isabs(name) or (len(name) > 1 and name[1] == ":"):
                raise RepoFetchError("Archive contains an absolute path entry.")

            parts = name.split("/")
            # parts[0] is GitHub's "<repo>-<ref>" wrapper; skip build dirs below it.
            if any(part in _SKIP_DIRS for part in parts[1:]):
                continue

            target = os.path.realpath(os.path.join(dest_root, *parts))
            if target != dest_root and not target.startswith(dest_root + os.sep):
                raise RepoFetchError("Archive contains a path traversal entry.")

            file_count += 1
            if file_count > max_files:
                raise RepoFetchError(
                    f"Repository contains more than {max_files} files."
                )

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(64 * 1024)
                    if not chunk:
                        break
                    total_written += len(chunk)
                    if total_written > max_bytes:
                        raise RepoFetchError(
                            f"Repository contents exceed the "
                            f"{settings.MAX_REPO_SIZE_MB} MB limit."
                        )
                    dst.write(chunk)

    if file_count == 0:
        raise RepoFetchError("Repository archive contained no scannable files.")

    # Unwrap GitHub's single top-level "<repo>-<ref>" directory.
    entries = os.listdir(dest_root)
    if len(entries) == 1:
        only = os.path.join(dest_root, entries[0])
        if os.path.isdir(only):
            return only
    return dest_root


# ── Dependency manifest discovery ─────────────────────────────

def read_dependency_file(root: str) -> tuple[str, str]:
    """
    Find the shallowest requirements.txt (preferred) or package.json in the
    repository and return (contents, ecosystem).  Returns ("", "pip") when
    neither is present, which the pipeline treats as "no dependency audit".
    """
    best: tuple[int, str, str] | None = None   # (depth, path, ecosystem)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        depth = os.path.relpath(dirpath, root).count(os.sep)
        for filename, ecosystem in _DEP_FILES:
            if filename not in filenames:
                continue
            # requirements.txt wins ties against package.json at equal depth.
            rank = (depth, 0 if ecosystem == "pip" else 1)
            if best is None or rank < (best[0], 0 if best[2] == "pip" else 1):
                best = (depth, os.path.join(dirpath, filename), ecosystem)

    if best is None:
        return "", "pip"

    try:
        with open(best[1], "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), best[2]
    except OSError as exc:
        logger.warning("could not read dependency file %s: %s", best[1], exc)
        return "", "pip"
