from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.config import Settings
from app.exceptions import GitHubFetchError, InvalidRepositoryUrlError, SourceFileNotFoundError
from app.schemas import SelectedSourceFile

logger = logging.getLogger(__name__)

GITHUB_API_VERSION = "2022-11-28"
GITHUB_API_BASE = "https://api.github.com"
SUPPORTED_EXTENSIONS: dict[str, int] = {
    ".py": 120,
    ".js": 110,
    ".ts": 108,
    ".tsx": 104,
    ".jsx": 102,
    ".go": 98,
    ".java": 96,
    ".cs": 92,
    ".php": 90,
    ".rb": 88,
    ".rs": 86,
    ".swift": 84,
    ".kt": 82,
    ".dart": 80,
    ".cpp": 76,
    ".cc": 74,
    ".cxx": 72,
    ".c": 70,
}

ENTRYPOINT_NAMES: dict[str, int] = {
    "main": 80,
    "app": 78,
    "server": 76,
    "index": 72,
    "api": 66,
    "application": 64,
    "program": 62,
    "handler": 58,
    "routes": 52,
}

EXCLUDED_DIR_PARTS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
    "target",
    "__pycache__",
    ".next",
    ".nuxt",
}

LOW_VALUE_PATH_PARTS = {
    "test",
    "tests",
    "spec",
    "specs",
    "examples",
    "example",
    "docs",
    "doc",
    "benchmark",
    "benchmarks",
    "migrations",
}

MINIFIED_RE = re.compile(r"(\.min\.|-min\.)")


@dataclass(frozen=True)
class ParsedGitHubRepo:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_github_repo_url(repo_url: str) -> ParsedGitHubRepo:
    """Parse and validate a GitHub repository URL."""

    parsed = urlparse(repo_url.strip())

    if parsed.scheme not in {"http", "https"}:
        raise InvalidRepositoryUrlError()

    host = parsed.netloc.lower()
    if host not in {"github.com", "www.github.com"}:
        raise InvalidRepositoryUrlError()

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        raise InvalidRepositoryUrlError()

    owner, repo = path_parts[0], path_parts[1]
    repo = repo.removesuffix(".git")

    if not owner or not repo:
        raise InvalidRepositoryUrlError()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise InvalidRepositoryUrlError()

    return ParsedGitHubRepo(owner=owner, repo=repo)


class GitHubRepositoryService:
    """Fetch repository metadata and select the most relevant source file."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "github-repo-analyzer-deepseek/1.0",
        }
        if self.settings.github_token and self.settings.github_token.get_secret_value().strip():
            headers["Authorization"] = f"Bearer {self.settings.github_token.get_secret_value()}"
        return headers

    async def fetch_primary_source_file(self, repo_url: str) -> SelectedSourceFile:
        parsed_repo = parse_github_repo_url(repo_url)

        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds,
            follow_redirects=True,
            headers=self._headers(),
        ) as client:
            repo_data = await self._get_repository_metadata(client, parsed_repo)
            default_branch = repo_data.get("default_branch") or "main"
            repo_name = repo_data.get("name") or parsed_repo.repo

            tree = await self._get_repository_tree(client, parsed_repo, default_branch)
            selected = self.select_primary_file(tree)
            if not selected:
                raise SourceFileNotFoundError()

            code = await self._download_blob(client, parsed_repo, selected["sha"])

        if len(code) > self.settings.max_code_chars_for_llm:
            code = code[: self.settings.max_code_chars_for_llm] + "\n\n/* TRUNCATED_FOR_LLM_CONTEXT_LIMIT */"

        return SelectedSourceFile(
            repo_name=repo_name,
            owner=parsed_repo.owner,
            repo=parsed_repo.repo,
            default_branch=default_branch,
            path=selected["path"],
            size=int(selected.get("size") or len(code.encode("utf-8"))),
            code=code,
        )

    async def _get_repository_metadata(
        self,
        client: httpx.AsyncClient,
        parsed_repo: ParsedGitHubRepo,
    ) -> dict[str, Any]:
        url = f"{GITHUB_API_BASE}/repos/{parsed_repo.owner}/{parsed_repo.repo}"
        response = await client.get(url)
        if response.status_code == 404:
            raise GitHubFetchError("Repository not found or not public.", status_code=404)
        if response.status_code == 403:
            raise GitHubFetchError("GitHub API rate limit reached or access denied.", status_code=429)
        if response.status_code >= 400:
            logger.warning("GitHub metadata fetch failed: %s %s", response.status_code, response.text[:300])
            raise GitHubFetchError("Failed to fetch repository metadata from GitHub.", status_code=502)
        return response.json()

    async def _get_repository_tree(
        self,
        client: httpx.AsyncClient,
        parsed_repo: ParsedGitHubRepo,
        default_branch: str,
    ) -> list[dict[str, Any]]:
        branch_ref = quote(default_branch, safe="")
        url = f"{GITHUB_API_BASE}/repos/{parsed_repo.owner}/{parsed_repo.repo}/git/trees/{branch_ref}"
        response = await client.get(url, params={"recursive": "1"})

        if response.status_code == 404:
            raise GitHubFetchError("Could not read the repository source tree.", status_code=404)
        if response.status_code == 403:
            raise GitHubFetchError("GitHub API rate limit reached or access denied.", status_code=429)
        if response.status_code >= 400:
            logger.warning("GitHub tree fetch failed: %s %s", response.status_code, response.text[:300])
            raise GitHubFetchError("Failed to fetch repository file tree from GitHub.", status_code=502)

        payload = response.json()
        if payload.get("truncated") is True:
            logger.info("GitHub tree response was truncated for %s", parsed_repo.full_name)
        return payload.get("tree", [])

    async def _download_blob(
        self,
        client: httpx.AsyncClient,
        parsed_repo: ParsedGitHubRepo,
        blob_sha: str,
    ) -> str:
        url = f"{GITHUB_API_BASE}/repos/{parsed_repo.owner}/{parsed_repo.repo}/git/blobs/{blob_sha}"

        response = await client.get(url)
        if response.status_code == 403:
            raise GitHubFetchError("GitHub API rate limit reached or access denied.", status_code=429)
        if response.status_code >= 400:
            logger.warning("GitHub blob download failed: %s %s", response.status_code, response.text[:300])
            raise GitHubFetchError("Failed to download the selected source code file.", status_code=502)

        payload = response.json()
        encoding = payload.get("encoding")
        content = payload.get("content")
        if encoding != "base64" or not isinstance(content, str):
            raise GitHubFetchError("Selected source file was not returned as base64 text.", status_code=502)

        try:
            return base64.b64decode(content, validate=False).decode("utf-8", errors="replace")
        except ValueError as exc:
            raise GitHubFetchError("Selected source file could not be decoded.", status_code=502) from exc

    def select_primary_file(self, tree: list[dict[str, Any]]) -> dict[str, Any] | None:
        candidates = []
        for item in tree:
            if item.get("type") != "blob":
                continue

            path = str(item.get("path", ""))
            size = int(item.get("size") or 0)
            if not path or size <= 0 or size > self.settings.max_source_file_bytes:
                continue
            if not self._is_supported_source_file(path):
                continue
            score = self._score_source_file(path, size)
            candidates.append((score, item))

        if not candidates:
            return None

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    def _is_supported_source_file(self, path: str) -> bool:
        lowered = path.lower()
        parts = lowered.split("/")
        if any(part in EXCLUDED_DIR_PARTS for part in parts):
            return False
        if MINIFIED_RE.search(lowered):
            return False
        return any(lowered.endswith(ext) for ext in SUPPORTED_EXTENSIONS)

    def _score_source_file(self, path: str, size: int) -> int:
        lowered = path.lower()
        parts = lowered.split("/")
        filename = parts[-1]
        stem = filename.rsplit(".", 1)[0]
        extension = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        depth = len(parts) - 1

        score = SUPPORTED_EXTENSIONS.get(extension, 0)
        score += ENTRYPOINT_NAMES.get(stem, 0)

        if depth == 0:
            score += 25
        elif depth == 1:
            score += 15
        elif depth == 2:
            score += 8
        else:
            score -= depth * 3

        if any(part in LOW_VALUE_PATH_PARTS for part in parts[:-1]):
            score -= 45

        if "src" in parts:
            score += 8
        if "api" in parts or "routes" in parts or "controllers" in parts:
            score += 6
        if "config" in stem or "settings" in stem:
            score -= 20
        if "__init__" == stem:
            score -= 50

        if 800 <= size <= 80_000:
            score += 10
        elif size < 300:
            score -= 30
        elif size > 150_000:
            score -= 20

        return score
