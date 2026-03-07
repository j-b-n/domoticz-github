# GitHub Stats Domoticz Plugin

This plugin exposes personal GitHub repository and GitHub Copilot billing data as Domoticz devices, authenticated with a plain **Personal Access Token (PAT)** — no GitHub App, no JWT, no OAuth2 flow.

## Quick Start

1. **Clone the repo:**
   ```bash
   git clone https://github.com/j-b-n/domoticz-github
   cd domoticz-github
   ```

2. **Install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create a PAT** at <https://github.com/settings/tokens?type=beta>
   - Fine-grained token permissions needed:
     - **Metadata: read** — implicit, always required
     - **Plan: read** — Copilot billing summary
     - **Contents: read** *(optional)* — private repository data

4. **Create a `.env` file** in the repo root (or copy `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env and set: GITHUB_PAT=ghp_...
   ```

5. **Test the connection:**
   ```bash
   python3 scripts/github_stats.py test
   ```

6. **Add the hardware in Domoticz UI** — configure `.env path` if the file is not in the plugin directory.

## Device Model

- **Repository metrics**: visible repos, private repos, total stars, total forks, open issues.
- **Account counters**: followers, following, public gists, public GitHub repos.
- **Copilot billing**: premium requests used, remaining, quota percentage, billable requests, net amount.
- **Language summary**: top 5 primary languages across all visible repositories.

The plugin uses 15 fixed device units — no dynamic creation when repositories change.

## Plugin Settings

- `Poll interval`: `1`, `5`, `10`, `30`, or `60` minutes (default: `5`).
- `.env path`: path to the credentials file. Defaults to the plugin directory.
- `Debug`: enable debug logging.

## Copilot Data Sources

The plugin tries the undocumented `/copilot_internal/user` endpoint first (near real-time), then falls back to the official billing summary API (`/users/{user}/settings/billing/usage/summary`) if the internal endpoint is unavailable.

> **Note:** Copilot data is only available for **GitHub Copilot Individual** plans. Business and Enterprise plan usage is reported at the organisation level and will show `0` via a personal token.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/github_stats.py test` | Rich CLI display of stats |
| `scripts/github_stats.py fetch` | Raw JSON snapshot (for scripting) |

For details on setup and the .env file, see [docs/BOOTSTRAP.md](docs/BOOTSTRAP.md).
