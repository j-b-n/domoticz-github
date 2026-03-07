from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import os

import requests
from dotenv import dotenv_values

API_BASE_URL = "https://api.github.com"
API_VERSION = "2022-11-28"
DEFAULT_PERSONAL_PREMIUM_REQUEST_QUOTA = 150.0
REQUEST_TIMEOUT = 20


class GitHubStatsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RepositoryStats:
    full_name: str
    private: bool
    stars: int
    forks: int
    open_issues: int
    language: str | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class RepositoryRollup:
    visible_repos: int
    private_repos: int
    public_repos: int
    total_stars: int
    total_forks: int
    open_issues: int
    top_languages: list[tuple[str, int]]
    most_starred_repo: str | None
    most_starred_stars: int
    recently_updated_repo: str | None
    recently_updated_at: str | None


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    login: str
    name: str | None
    public_repos: int
    followers: int
    following: int
    public_gists: int
    created_at: str | None


@dataclass(frozen=True, slots=True)
class CopilotBillingSummary:
    available: bool
    user: str
    year: int | None
    month: int | None
    included_quota: float | None
    total_requests: float
    billable_requests: float
    total_cost: float
    used_quota_percent: float | None
    remaining_quota: float | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PersonalStatsSnapshot:
    collected_at: str
    account: AccountSnapshot
    repositories: list[RepositoryStats]
    repository_rollup: RepositoryRollup
    copilot_billing: CopilotBillingSummary


def env_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Any:
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        timeout=timeout,
    )
    if response.status_code >= 400:
        detail = response.text.strip()
        raise GitHubStatsError(f"GitHub API {response.status_code} for {url}: {detail}")
    if response.text.strip():
        return response.json()
    return None


def load_env_values(env_path: Path) -> dict[str, str]:
    if not os.path.exists(env_path):
        raise GitHubStatsError(f"Environment file not found: {env_path}")
    return {
        key: str(value)
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }


def load_pat(env_path: Path) -> str:
    """Load the GitHub Personal Access Token exclusively from the .env file."""
    values = load_env_values(env_path)
    for key in ("GITHUB_PAT", "GITHUB_TOKEN"):
        token = values.get(key, "").strip()
        if token:
            return token
    loaded_keys = ", ".join(sorted(values.keys()))
    raise GitHubStatsError(
        f"Missing GITHUB_PAT in {env_path}. "
        f"Found keys: {loaded_keys if loaded_keys else '(none)'}. "
        f"Add GITHUB_PAT=ghp_... to the .env file."
    )


def load_premium_request_quota(env_path: Path) -> float | None:
    values = load_env_values(env_path)
    raw_value = values.get("GITHUB_COPILOT_MONTHLY_QUOTA")
    if raw_value:
        try:
            return float(raw_value)
        except ValueError:
            return None
    return DEFAULT_PERSONAL_PREMIUM_REQUEST_QUOTA


def fetch_user(pat: str) -> dict[str, Any]:
    """Fetch the authenticated user's profile."""
    return request_json("GET", f"{API_BASE_URL}/user", headers=env_headers(pat))


def fetch_all_repos(pat: str) -> list[dict[str, Any]]:
    """Fetch all repositories accessible to the PAT (owned + member, sorted by update time)."""
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = request_json(
            "GET",
            f"{API_BASE_URL}/user/repos?per_page=100&page={page}&type=all&sort=updated",
            headers=env_headers(pat),
        )
        repositories.extend(batch or [])
        if len(batch or []) < 100:
            return repositories
        page += 1


def fetch_copilot_internal(pat: str) -> dict[str, Any]:
    """Fetch the near-real-time Copilot quota snapshot from the internal API."""
    return request_json(
        "GET",
        f"{API_BASE_URL}/copilot_internal/user",
        headers=env_headers(pat),
    )


def fetch_personal_copilot_billing(pat: str, username: str) -> dict[str, Any]:
    """Fetch Copilot usage from the official billing summary API (may lag by hours)."""
    return request_json(
        "GET",
        f"{API_BASE_URL}/users/{username}/settings/billing/usage/summary",
        headers=env_headers(pat),
    )


def normalize_repository(repository: dict[str, Any]) -> RepositoryStats:
    return RepositoryStats(
        full_name=str(repository.get("full_name", "-")),
        private=bool(repository.get("private")),
        stars=int(repository.get("stargazers_count", 0) or 0),
        forks=int(repository.get("forks_count", 0) or 0),
        open_issues=int(repository.get("open_issues_count", 0) or 0),
        language=str(repository.get("language")) if repository.get("language") else None,
        updated_at=str(repository.get("updated_at")) if repository.get("updated_at") else None,
    )


def summarize_repositories(repositories: list[RepositoryStats]) -> RepositoryRollup:
    total_stars = sum(repository.stars for repository in repositories)
    total_forks = sum(repository.forks for repository in repositories)
    total_open_issues = sum(repository.open_issues for repository in repositories)
    private_count = sum(1 for repository in repositories if repository.private)
    languages: dict[str, int] = {}
    for repository in repositories:
        if repository.language:
            languages[repository.language] = languages.get(repository.language, 0) + 1

    top_languages = sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:5]
    most_starred_repo = max(repositories, key=lambda item: item.stars, default=None)
    recently_updated_repo = max(
        repositories,
        key=lambda item: item.updated_at or "",
        default=None,
    )

    return RepositoryRollup(
        visible_repos=len(repositories),
        private_repos=private_count,
        public_repos=len(repositories) - private_count,
        total_stars=total_stars,
        total_forks=total_forks,
        open_issues=total_open_issues,
        top_languages=top_languages,
        most_starred_repo=most_starred_repo.full_name if most_starred_repo else None,
        most_starred_stars=most_starred_repo.stars if most_starred_repo else 0,
        recently_updated_repo=recently_updated_repo.full_name if recently_updated_repo else None,
        recently_updated_at=recently_updated_repo.updated_at if recently_updated_repo else None,
    )


def build_account_snapshot(payload: dict[str, Any]) -> AccountSnapshot:
    return AccountSnapshot(
        login=str(payload.get("login", "-")),
        name=str(payload.get("name")) if payload.get("name") else None,
        public_repos=int(payload.get("public_repos", 0) or 0),
        followers=int(payload.get("followers", 0) or 0),
        following=int(payload.get("following", 0) or 0),
        public_gists=int(payload.get("public_gists", 0) or 0),
        created_at=str(payload.get("created_at")) if payload.get("created_at") else None,
    )


def summarize_personal_copilot_billing(env_path: Path, payload: dict[str, Any]) -> CopilotBillingSummary:
    usage_items = payload.get("usageItems") or []
    total_requests = sum(float(item.get("grossQuantity", 0) or 0) for item in usage_items)
    total_billable_requests = sum(float(item.get("netQuantity", 0) or 0) for item in usage_items)
    total_cost = sum(float(item.get("netAmount", 0) or 0) for item in usage_items)
    monthly_quota = load_premium_request_quota(env_path)
    usage_percentage = None
    remaining_quota = None
    if monthly_quota and monthly_quota > 0:
        usage_percentage = min((total_requests / monthly_quota) * 100.0, 100.0)
        remaining_quota = max(monthly_quota - total_requests, 0.0)
    time_period = payload.get("timePeriod") or {}
    return CopilotBillingSummary(
        available=True,
        user=str(payload.get("user", "-")),
        year=int(time_period.get("year")) if time_period.get("year") else None,
        month=int(time_period.get("month")) if time_period.get("month") else None,
        included_quota=monthly_quota,
        total_requests=total_requests,
        billable_requests=total_billable_requests,
        total_cost=total_cost,
        used_quota_percent=usage_percentage,
        remaining_quota=remaining_quota,
    )


def unavailable_copilot_summary(reason: str) -> CopilotBillingSummary:
    return CopilotBillingSummary(
        available=False,
        user="-",
        year=None,
        month=None,
        included_quota=None,
        total_requests=0.0,
        billable_requests=0.0,
        total_cost=0.0,
        used_quota_percent=None,
        remaining_quota=None,
        reason=reason,
    )


def collect_personal_stats(env_path: Path) -> PersonalStatsSnapshot:
    pat = load_pat(env_path)
    user_payload = fetch_user(pat)
    username = str(user_payload.get("login", ""))

    raw_repos = fetch_all_repos(pat)
    repositories = [normalize_repository(item) for item in raw_repos]

    # Try the near-real-time internal API first, fall back to billing summary API
    try:
        internal = fetch_copilot_internal(pat)
        copilot_billing = _summarize_copilot_internal(env_path, internal, username)
    except GitHubStatsError:
        try:
            billing_payload = fetch_personal_copilot_billing(pat, username)
            copilot_billing = summarize_personal_copilot_billing(env_path, billing_payload)
        except GitHubStatsError as error:
            copilot_billing = unavailable_copilot_summary(str(error))

    return PersonalStatsSnapshot(
        collected_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        account=build_account_snapshot(user_payload),
        repositories=repositories,
        repository_rollup=summarize_repositories(repositories),
        copilot_billing=copilot_billing,
    )


def _summarize_copilot_internal(
    env_path: Path, payload: dict[str, Any], username: str
) -> CopilotBillingSummary:
    """Build a CopilotBillingSummary from the /copilot_internal/user response."""
    premium = (payload.get("quota_snapshots") or {}).get("premium_interactions") or {}
    if premium.get("unlimited"):
        return CopilotBillingSummary(
            available=True,
            user=username,
            year=None,
            month=None,
            included_quota=None,
            total_requests=0.0,
            billable_requests=0.0,
            total_cost=0.0,
            used_quota_percent=None,
            remaining_quota=None,
            reason="Unlimited plan",
        )
    if not premium:
        raise GitHubStatsError("No premium_interactions quota in internal API response")

    monthly_quota = load_premium_request_quota(env_path)
    entitlement = float(premium.get("entitlement") or monthly_quota or DEFAULT_PERSONAL_PREMIUM_REQUEST_QUOTA)
    remaining = float(premium.get("quota_remaining", 0) or 0)
    used = entitlement - remaining
    usage_percentage = min((used / entitlement) * 100.0, 100.0) if entitlement > 0 else None

    now = datetime.now(UTC)
    return CopilotBillingSummary(
        available=True,
        user=username,
        year=now.year,
        month=now.month,
        included_quota=entitlement,
        total_requests=used,
        billable_requests=0.0,
        total_cost=0.0,
        used_quota_percent=usage_percentage,
        remaining_quota=remaining,
    )