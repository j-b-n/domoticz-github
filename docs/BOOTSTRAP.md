# Setup Guide

This document explains how to create a GitHub Personal Access Token (PAT) and configure the plugin.

## Why a PAT?

A PAT is a simple, long-lived credential that grants read-only access to your GitHub account data. The plugin only needs to *read* your profile, repositories, and Copilot billing numbers — no write access, no app installation, no OAuth flow.

## Creating a Fine-Grained PAT (recommended)

1. Go to <https://github.com/settings/tokens?type=beta>
2. Click **Generate new token**.
3. Give it a name, e.g. *Domoticz GitHub Stats*.
4. Set **Expiration** to your preferred duration (1 year is typical).
5. Under **Account permissions**, set:
   - **Metadata** — Read (implicit, cannot be unchecked)
   - **Plan** — Read (needed for Copilot billing summary)
6. Under **Repository access**, choose:
   - *Public repositories only* — if you only want public repo stats.
   - *All repositories* (or selected) and add **Contents: read** — if you want private repos included.
7. Click **Generate token** and copy the value immediately.

## Classic PAT (alternative)

If you prefer a classic PAT:

1. Go to <https://github.com/settings/tokens>
2. Click **Generate new token (classic)**.
3. Select scopes:
   - *(no scopes)* — public repos + profile + Copilot billing.
   - `repo` — adds private repository data.
4. Generate and copy the token.

## Configure the plugin

Create a `.env` file in the plugin directory (copy `.env.example` as a starting point):

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
GITHUB_PAT=ghp_YourTokenHere

# Optional: override the Copilot monthly quota used for the % bar (default: 150)
# GITHUB_COPILOT_MONTHLY_QUOTA=300
```

## Test before deploying

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/github_stats.py test
```

A successful run shows your account snapshot, repository rollup, and Copilot billing panel.

## Deploy to Domoticz

```bash
cp plugin.py shared/github_stats_shared.py ~/.domoticz/plugins/GitHub_Stats/
cp .env ~/.domoticz/plugins/GitHub_Stats/
```

Restart Domoticz, then add **GitHub Stats** as a new hardware device. The `.env path` parameter defaults to the plugin directory; change it only if you placed the file elsewhere.

## Copilot data notes

- Copilot data is only available for **GitHub Copilot Individual** plans.
- The plugin tries `/copilot_internal/user` first (near real-time), then falls back to the official billing summary API.
- If neither returns data, the Copilot devices will show `0`; the profile and repository devices are unaffected.
- To adjust the monthly quota displayed as a percentage, set `GITHUB_COPILOT_MONTHLY_QUOTA` in `.env`.
