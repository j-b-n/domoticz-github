# Domoticz GitHub Stats Plugin — Developer Instructions

## Project Overview

A **Domoticz hardware plugin** that exposes GitHub repository metrics and Copilot billing data as device units via a **GitHub Personal Access Token (PAT)**. Fixed 15-unit aggregate model (not dynamic per-repository).

### Core Files
- **plugin.py** — Main `BasePlugin` with lifecycle hooks, heartbeat polling, state caching
- **shared/github_stats_shared.py** — GitHub API logic (PAT auth, pagination, data models)
- **scripts/github_stats.py** — CLI for testing and fetching stats (`test` / `fetch` commands)
- **scripts/copilot_pace.py** — Standalone Copilot pacing bar (mirrors copilot-pacer extension interface)

## Quick Start

**Setup** (create `.env` with your PAT):
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env
# Edit .env: set GITHUB_PAT=ghp_...
python3 scripts/github_stats.py test
```

**Deploy** to Domoticz:
```bash
cp plugin.py shared/github_stats_shared.py .env ~/.domoticz/plugins/GitHub_Stats/
```

## Key Patterns

### Heartbeat Polling
- 30-second heartbeat cycle; compute `poll_interval_beats()` to trigger at set intervals (e.g., 5 min = 10 beats)
- Avoids Domoticz "heartbeat too slow" warnings

### Device Model
- **15 fixed units** (never dynamic) — repos, stars, forks, followers, Copilot metrics, language summary
- State cached in `Domoticz.Configuration()` and restored on restart
- Custom PNG icons (64×64, RGBA) auto-registered at plugin start

### GitHub API
- **Authentication**: GitHub PAT (`GITHUB_PAT` in `.env` or environment)
- **REST only** (no GraphQL); pagination manual, 100 items/page
- Two Copilot data sources: `/copilot_internal/user` (real-time, preferred) → `/users/{user}/settings/billing/usage/summary` (fallback)
- Error handling: Custom `GitHubStatsError` exception logged to unit 1
- All text fields truncated to 255 chars (Domoticz limit)

## Configuration

**Domoticz UI Settings**:
- Poll interval: 1, 5, 10, 30, or 60 minutes (default: 5)
- .env path: Path to credentials file (default: plugin directory)
- Debug: Enable debug logging

**.env Variables**:
Required: `GITHUB_PAT`  
Optional: `GITHUB_COPILOT_MONTHLY_QUOTA` (default: 150)  
See [.env.example](.env.example) for the full template.

## Dependencies
- **python-dotenv** — .env loading
- **requests** — HTTP
- **rich** — CLI UI

## Common Issues

1. **Missing PAT** — `GITHUB_PAT` not set or .env not found; check `.env path` plugin parameter
2. **Copilot billing 403** — Token lacks `Plan: read` permission; add it to fine-grained PAT
3. **Only public repos** — Add `Contents: read` + repository access scope for private repos
4. **Heartbeat math** — 5-min poll at 30s heartbeat = 10 beats

## File Structure

```
.
├── plugin.py                    # Main BasePlugin
├── shared/github_stats_shared.py # GitHub API logic (PAT auth, data models)
├── scripts/github_stats.py      # CLI: test / fetch commands
├── scripts/copilot_pace.py      # Standalone Copilot pacing bar
├── requirements.txt
├── .env (git-ignored)           # Credentials (GITHUB_PAT=ghp_...)
├── .env.example                 # Template
├── README.md
└── docs/BOOTSTRAP.md            # Setup guide
```

## Development

1. Edit `plugin.py` or `shared/github_stats_shared.py`
2. Test: copy to `~/.domoticz/plugins/GitHub_Stats/` and check logs
3. Update docs if needed
4. Never commit `.env`

---

**Last Updated**: 7 March 2026 | **Framework**: DomoticzEx Python Plugin | **Python**: 3.9+
