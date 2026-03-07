#!/usr/bin/env python3
"""
github_stats.py — PAT-based CLI for GitHub Stats

Commands:
  test    Fetch and display GitHub profile, repository rollup, and Copilot billing.
  fetch   Print the raw JSON snapshot (useful for scripting).

Authentication:
  Set GITHUB_PAT in the environment or add it to .env (same file used by the plugin):
    GITHUB_PAT=ghp_...

  Required fine-grained PAT permissions:
    - Metadata: read  (implicit, always required)
    - Plan: read      (for Copilot billing summary)
    - Contents: read  (add to include private repository data)

  A classic PAT with no scopes also works for public data + billing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

SHARED_MODULE_PATH = Path(__file__).resolve().parent.parent / "shared"
if str(SHARED_MODULE_PATH) not in sys.path:
    sys.path.insert(0, str(SHARED_MODULE_PATH))

import github_stats_shared as shared

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
console = Console()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def render_banner(title: str, subtitle: str) -> None:
    text = Text()
    text.append(f"{title}\n", style="bold white")
    text.append(subtitle, style="cyan")
    console.print(Panel.fit(text, border_style="bright_blue", box=box.DOUBLE_EDGE))


def _kv_table(title: str, values: dict[str, Any], *, style: str = "cyan") -> None:
    table = Table(title=title, box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value", style=style)
    for key, value in values.items():
        table.add_row(key, str(value))
    console.print(table)


def print_account_snapshot(account: shared.AccountSnapshot) -> None:
    _kv_table(
        "Personal Account Snapshot",
        {
            "Login":        account.login,
            "Name":         account.name or "-",
            "Public repos": account.public_repos,
            "Followers":    account.followers,
            "Following":    account.following,
            "Public gists": account.public_gists,
            "Created":      account.created_at or "-",
        },
        style="green",
    )


def print_repository_rollup(rollup: shared.RepositoryRollup) -> None:
    top_langs = ", ".join(
        f"{name} ({count})" for name, count in rollup.top_languages
    ) or "-"
    _kv_table(
        "Repository Rollup",
        {
            "Visible repos": rollup.visible_repos,
            "Private repos": rollup.private_repos,
            "Public repos":  rollup.public_repos,
            "Total stars":   rollup.total_stars,
            "Total forks":   rollup.total_forks,
            "Open issues":   rollup.open_issues,
            "Top languages": top_langs,
            "Most starred":  f"{rollup.most_starred_repo} ({rollup.most_starred_stars}*)" if rollup.most_starred_repo else "-",
        },
    )


def print_repositories_table(repositories: list[shared.RepositoryStats]) -> None:
    table = Table(title="Repositories (most recently updated)", box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="bold white")
    table.add_column("Private", justify="center")
    table.add_column("Stars", justify="right")
    table.add_column("Forks", justify="right")
    table.add_column("Language")
    table.add_column("Updated")

    for r in repositories[:10]:
        table.add_row(
            r.full_name,
            "yes" if r.private else "no",
            str(r.stars),
            str(r.forks),
            r.language or "-",
            (r.updated_at or "-")[:10],
        )
    if len(repositories) > 10:
        console.print(f"  [dim]... {len(repositories) - 10} more repositories not shown[/dim]")
    console.print(table)


def print_copilot_summary(copilot: shared.CopilotBillingSummary) -> None:
    if not copilot.available:
        console.print(
            Panel.fit(
                copilot.reason or "Copilot billing data is unavailable.",
                title="Copilot Billing Unavailable",
                border_style="yellow",
            )
        )
        return

    if copilot.reason == "Unlimited plan":
        _kv_table("Copilot Premium Requests", {"Status": "Unlimited plan"}, style="magenta")
        return

    pct = copilot.used_quota_percent
    _kv_table(
        "Copilot Premium Request Summary",
        {
            "User":               copilot.user,
            "Year / Month":       f"{copilot.year} / {copilot.month}" if copilot.year else "current",
            "Requests used":      f"{copilot.total_requests:.0f}",
            "Included quota":     f"{copilot.included_quota:.0f}" if copilot.included_quota else "unknown",
            "Used %":             f"{pct:.1f}%" if pct is not None else "unknown",
            "Remaining":          f"{copilot.remaining_quota:.0f}" if copilot.remaining_quota is not None else "unknown",
            "Billable requests":  f"{copilot.billable_requests:.0f}",
            "Net amount":         f"${copilot.total_cost:.2f}",
        },
        style="magenta",
    )

    if pct is not None and copilot.included_quota:
        label    = f"Copilot quota: {pct:.1f}%"
        subtitle = f"{copilot.total_requests:.0f} of {copilot.included_quota:.0f} requests used"
        bar      = ProgressBar(
            total=copilot.included_quota,
            completed=min(copilot.total_requests, copilot.included_quota),
            width=48,
        )
        console.print(Panel.fit(bar, title=label, subtitle=subtitle, border_style="green"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def handle_test(args: argparse.Namespace) -> int:
    render_banner(
        "GitHub Stats",
        "Fetching profile, repository, and Copilot data via PAT.",
    )

    with console.status("Loading credentials and fetching data...", spinner="dots"):
        try:
            snapshot = shared.collect_personal_stats(ENV_PATH)
        except shared.GitHubStatsError as error:
            console.print(Panel.fit(str(error), title="Error", border_style="red"))
            return 1

    console.print(f"\nAuthenticated as [bold green]{snapshot.account.login}[/bold green]\n")

    print_account_snapshot(snapshot.account)
    print_repository_rollup(snapshot.repository_rollup)
    print_repositories_table(snapshot.repositories)
    print_copilot_summary(snapshot.copilot_billing)

    console.print(
        Panel.fit(
            f"Collected at: {snapshot.collected_at}\n"
            f"Repositories: {snapshot.repository_rollup.visible_repos} total "
            f"({snapshot.repository_rollup.private_repos} private)",
            title="Summary",
            border_style="bright_blue",
        )
    )
    return 0


def handle_fetch(args: argparse.Namespace) -> int:
    try:
        snapshot = shared.collect_personal_stats(ENV_PATH)
    except shared.GitHubStatsError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1

    rollup  = snapshot.repository_rollup
    account = snapshot.account
    copilot = snapshot.copilot_billing

    output = {
        "collected_at": snapshot.collected_at,
        "account": {
            "login":        account.login,
            "name":         account.name,
            "public_repos": account.public_repos,
            "followers":    account.followers,
            "following":    account.following,
            "public_gists": account.public_gists,
        },
        "repository_rollup": {
            "visible_repos":      rollup.visible_repos,
            "private_repos":      rollup.private_repos,
            "public_repos":       rollup.public_repos,
            "total_stars":        rollup.total_stars,
            "total_forks":        rollup.total_forks,
            "open_issues":        rollup.open_issues,
            "top_languages":      rollup.top_languages,
            "most_starred_repo":  rollup.most_starred_repo,
            "most_starred_stars": rollup.most_starred_stars,
        },
        "copilot_billing": {
            "available":          copilot.available,
            "total_requests":     copilot.total_requests,
            "included_quota":     copilot.included_quota,
            "used_percent":       copilot.used_quota_percent,
            "remaining_quota":    copilot.remaining_quota,
            "billable_requests":  copilot.billable_requests,
            "total_cost":         copilot.total_cost,
        },
    }
    print(json.dumps(output, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub profile, repository, and Copilot stats via a Personal Access Token.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "test",
        help="Display GitHub stats in a human-readable rich layout.",
    )
    subparsers.add_parser(
        "fetch",
        help="Print the stats snapshot as JSON (useful for scripting).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "test":
            return handle_test(args)
        if args.command == "fetch":
            return handle_fetch(args)
        parser.error(f"Unsupported command: {args.command}")
        return 2
    except KeyboardInterrupt:
        console.print("\nInterrupted.", style="bold yellow")
        return 130
    except requests.RequestException as error:
        console.print(Panel.fit(f"Network error: {error}", title="Error", border_style="red"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
