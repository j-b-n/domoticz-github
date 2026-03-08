""" 
<plugin key="GitHubStats" name="GitHub Stats" author="j-b-n"
        version="0.2.0"
        wikilink="https://github.com/j-b-n/domoticz-github">
    <description>
        <h2>GitHub Stats</h2>
        <p>Collects personal GitHub repository and Copilot billing statistics using a GitHub Personal Access Token (PAT).</p>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Repository counts, stars, forks, and open issues as numeric sensors.</li>
            <li>Personal account metrics such as followers, following, public gists, and public repositories.</li>
            <li>Copilot premium request usage, billable requests, quota percentage, and billing amount.</li>
            <li>Text summary for repository languages.</li>
            <li>Default .env path is the plugin directory, but can be customized in parameters.</li>
        </ul>
        <h3>Setup</h3>
        <p>Create a <b>.env</b> file in the plugin directory containing: <b>GITHUB_PAT=ghp_...</b></p>
        <p>The PAT needs <b>Metadata: read</b> (always implicit) and optionally <b>Plan: read</b> for Copilot billing.</p>
    </description>
    <params>
        <param field="Mode1" label="Poll interval" width="140px" required="true">
            <options>
                <option label="1 minute" value="1"/>
                <option label="5 minutes" value="5" default="true"/>
                <option label="10 minutes" value="10"/>
                <option label="30 minutes" value="30"/>
                <option label="60 minutes" value="60"/>
            </options>
        </param>
        <param field="Mode2" label=".env path" width="360px" required="false"
               default=""/>
        <param field="Mode6" label="Debug" width="90px">
            <options>
                <option label="Normal" value="Normal" default="true"/>
                <option label="Debug" value="Debug"/>
            </options>
        </param>
    </params>
</plugin>
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import os
import os.path

import DomoticzEx as Domoticz

from shared.github_stats_shared import GitHubStatsError, PersonalStatsSnapshot, collect_personal_stats

HEARTBEAT_SECONDS = 30
DEFAULT_POLL_MINUTES = 5
MINUTES_OPTIONS = {1, 5, 10, 30, 60}

# Icon set name (from github_stats_icons.zip)
ICON_SET_NAME = "GitHub"

# DomoticzEx: Single parent device hosting 15 units
DEVICE_ID = "GitHub_Stats"

# Unit IDs within the parent device
DEVICE_REPO_COUNT = 1
DEVICE_PRIVATE_REPOS = 2
DEVICE_TOTAL_STARS = 3
DEVICE_TOTAL_FORKS = 4
DEVICE_OPEN_ISSUES = 5
DEVICE_FOLLOWERS = 6
DEVICE_FOLLOWING = 7
DEVICE_PUBLIC_GISTS = 8
DEVICE_PUBLIC_REPOS = 9
DEVICE_COPILOT_REQUESTS = 10
DEVICE_COPILOT_BILLABLE = 11
DEVICE_COPILOT_USED_PERCENT = 12
DEVICE_COPILOT_REMAINING = 13
DEVICE_COPILOT_NET_AMOUNT = 14
DEVICE_LANGUAGE_SUMMARY = 15


class BasePlugin:
    def __init__(self) -> None:
        self.heartbeat_count = 0

    def onStart(self) -> None:
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(2 + 4 + 8)

        Domoticz.Log("Starting GitHub Stats")
        
        # Load custom icon set
        Domoticz.Image(f'{ICON_SET_NAME}.zip').Create()
        
        env_path = self.resolve_env_path()
        if not env_path.exists():
            Domoticz.Log(f"Using .env path: {env_path}")
            Domoticz.Error(f".env file NOT found at {env_path}")
        
        Domoticz.Heartbeat(HEARTBEAT_SECONDS)
        self.ensure_devices()
        self.restore_cached_state()
        self.refresh_stats("startup")

    def onHeartbeat(self) -> None:
        self.heartbeat_count += 1
        if self.heartbeat_count % self.poll_interval_beats() != 0:
            return
        self.refresh_stats("scheduled")

    def onStop(self) -> None:
        Domoticz.Log("GitHub Stats stopped cleanly")

    def ensure_devices(self) -> None:
        self.ensure_unit(DEVICE_REPO_COUNT, "Visible Repositories", "Custom", "repos")
        self.ensure_unit(DEVICE_PRIVATE_REPOS, "Private Repositories", "Custom", "repos")
        self.ensure_unit(DEVICE_TOTAL_STARS, "Total Stars", "Custom", "stars")
        self.ensure_unit(DEVICE_TOTAL_FORKS, "Total Forks", "Custom", "forks")
        self.ensure_unit(DEVICE_OPEN_ISSUES, "Open Issues", "Custom", "issues")
        self.ensure_unit(DEVICE_FOLLOWERS, "Followers", "Custom", "users")
        self.ensure_unit(DEVICE_FOLLOWING, "Following", "Custom", "users")
        self.ensure_unit(DEVICE_PUBLIC_GISTS, "Public Gists", "Custom", "gists")
        self.ensure_unit(DEVICE_PUBLIC_REPOS, "Public GitHub Repos", "Custom", "repos")
        self.ensure_unit(DEVICE_COPILOT_REQUESTS, "Copilot Requests", "Custom", "req")
        self.ensure_unit(DEVICE_COPILOT_BILLABLE, "Copilot Billable Requests", "Custom", "req")
        self.ensure_unit(DEVICE_COPILOT_USED_PERCENT, "Copilot Used Quota", "Custom", "%", subtype=6)
        self.ensure_unit(DEVICE_COPILOT_REMAINING, "Copilot Remaining Quota", "Custom", "req")
        self.ensure_unit(DEVICE_COPILOT_NET_AMOUNT, "Copilot Net Amount", "Custom", "$")
        # Language Summary uses Text type
        self.ensure_unit(DEVICE_LANGUAGE_SUMMARY, "Language Summary", "Text")

    def ensure_unit(self, unit: int, name: str, unit_type: str, unit_label: str | None = None, subtype: int | None = None) -> None:
        """Ensure a unit exists within the parent device."""
        if DEVICE_ID in Devices and unit in Devices[DEVICE_ID].Units:
            return
        
        try:
            # Get icon ID from the loaded icon set
            icon_id = Images['GitHub'].ID if 'GitHub' in Images else 0
            
            if unit_type == "Text":
                Domoticz.Unit(
                    Name=name,
                    Unit=unit,
                    DeviceID=DEVICE_ID,
                    TypeName="Text",
                    Image=icon_id,
                    Used=1,
                ).Create()
            else:  # Custom sensor
                # Use provided subtype or default to 31
                actual_subtype = subtype if subtype is not None else 31
                options = {"Custom": f"1;{unit_label}"} if unit_label else {"Custom": "1;"}
                Domoticz.Unit(
                    Name=name,
                    Unit=unit,
                    DeviceID=DEVICE_ID,
                    Type=243,
                    Subtype=actual_subtype,
                    Options=options,
                    Image=icon_id,
                    Used=1,
                ).Create()
            Domoticz.Log(f"Created unit {unit} ({name}) in device {DEVICE_ID}")
        except Exception as e:
            Domoticz.Error(f"Failed to create unit {unit} ({name}): {e}")

    def refresh_stats(self, reason: str) -> None:
        env_path = self.resolve_env_path()
        try:
            if not env_path.exists():
                raise GitHubStatsError(f".env file not found at {env_path}")
            snapshot = collect_personal_stats(env_path)
        except GitHubStatsError as error:
            message = self.truncate_text(f"Error during {reason} sync: {error}")
            self.update_cached_state(error=message)
            Domoticz.Error(str(error))
            return

        self.apply_snapshot(snapshot)
        self.update_cached_state(error="")
        Domoticz.Debug(
            f"GitHub sync completed for {snapshot.account.login}; next poll in {self.poll_interval_minutes()} minute(s)."
        )

    def resolve_env_path(self) -> Path:
        raw_path = Parameters["Mode2"].strip()
        
        # If Mode2 is empty, use default in plugin directory
        if not raw_path:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            return (Path(plugin_dir) / ".env").resolve()
        
        # If Mode2 is a relative path (like ".env"), treat it as relative to plugin directory
        if not os.path.isabs(raw_path) and not raw_path.startswith("~"):
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            return (Path(plugin_dir) / raw_path).resolve()
        
        # If Mode2 is absolute or starts with ~, use as-is
        return Path(raw_path).expanduser().resolve()

    def poll_interval_minutes(self) -> int:
        try:
            requested = int(Parameters["Mode1"])
        except (KeyError, ValueError):
            return DEFAULT_POLL_MINUTES
        if requested not in MINUTES_OPTIONS:
            return DEFAULT_POLL_MINUTES
        return requested

    def poll_interval_beats(self) -> int:
        return max(1, int((self.poll_interval_minutes() * 60) / HEARTBEAT_SECONDS))

    def apply_snapshot(self, snapshot: PersonalStatsSnapshot) -> None:
        rollup = snapshot.repository_rollup
        account = snapshot.account
        copilot = snapshot.copilot_billing

        self.update_device(DEVICE_REPO_COUNT, 0, str(rollup.visible_repos))
        self.update_device(DEVICE_PRIVATE_REPOS, 0, str(rollup.private_repos))
        self.update_device(DEVICE_TOTAL_STARS, 0, str(rollup.total_stars))
        self.update_device(DEVICE_TOTAL_FORKS, 0, str(rollup.total_forks))
        self.update_device(DEVICE_OPEN_ISSUES, 0, str(rollup.open_issues))
        self.update_device(DEVICE_FOLLOWERS, 0, str(account.followers))
        self.update_device(DEVICE_FOLLOWING, 0, str(account.following))
        self.update_device(DEVICE_PUBLIC_GISTS, 0, str(account.public_gists))
        self.update_device(DEVICE_PUBLIC_REPOS, 0, str(account.public_repos))
        self.update_device(DEVICE_COPILOT_REQUESTS, 0, self.format_float(copilot.total_requests))
        self.update_device(DEVICE_COPILOT_BILLABLE, 0, self.format_float(copilot.billable_requests))
        self.update_device(
            DEVICE_COPILOT_USED_PERCENT,
            0,
            self.format_float(copilot.used_quota_percent, default="0"),
        )
        self.update_device(
            DEVICE_COPILOT_REMAINING,
            0,
            self.format_float(copilot.remaining_quota, default="0"),
        )
        self.update_device(DEVICE_COPILOT_NET_AMOUNT, 0, f"{copilot.total_cost:.2f}")
        self.update_device(DEVICE_LANGUAGE_SUMMARY, 0, self.build_language_summary(snapshot))

    def build_repo_summary(self, snapshot: PersonalStatsSnapshot) -> str:
        top_repositories = sorted(snapshot.repositories, key=lambda item: (-item.stars, item.full_name))[:5]
        if not top_repositories:
            return "No repositories visible to the app."
        summary = " | ".join(
            f"{repository.full_name} {repository.stars}* {repository.open_issues} issues"
            for repository in top_repositories
        )
        return self.truncate_text(summary)

    def build_language_summary(self, snapshot: PersonalStatsSnapshot) -> str:
        top_languages = snapshot.repository_rollup.top_languages
        if not top_languages:
            return "No primary languages reported by GitHub."
        return self.truncate_text(
            " | ".join(f"{language} {count}" for language, count in top_languages)
        )

    def build_copilot_summary(self, snapshot: PersonalStatsSnapshot) -> str:
        copilot = snapshot.copilot_billing
        if not copilot.available:
            return self.truncate_text(copilot.reason or "Copilot billing data is unavailable.")

        used_percent = f"{copilot.used_quota_percent:.1f}%" if copilot.used_quota_percent is not None else "n/a"
        included = self.format_float(copilot.included_quota, default="n/a")
        remaining = self.format_float(copilot.remaining_quota, default="n/a")
        summary = (
            f"{self.format_float(copilot.total_requests)} of {included} requests used, "
            f"{used_percent}, billable {self.format_float(copilot.billable_requests)}, "
            f"remaining {remaining}, ${copilot.total_cost:.2f}"
        )
        return self.truncate_text(summary)

    def build_account_summary(self, snapshot: PersonalStatsSnapshot) -> str:
        account = snapshot.account
        summary = (
            f"{account.login} | public repos {account.public_repos} | followers {account.followers} | "
            f"following {account.following} | gists {account.public_gists}"
        )
        return self.truncate_text(summary)

    def update_device(self, unit: int, n_value: int, s_value: str) -> None:
        """Update a unit value in the parent device."""
        if DEVICE_ID not in Devices or unit not in Devices[DEVICE_ID].Units:
            return
        unit_obj = Devices[DEVICE_ID].Units[unit]
        if unit_obj.nValue == n_value and str(unit_obj.sValue) == s_value:
            return
        try:
            unit_obj.nValue = n_value
            unit_obj.sValue = s_value
            unit_obj.Update(Log=False)
        except Exception as e:
            Domoticz.Error(f"Failed to update unit {unit}: {e}")

    def restore_cached_state(self) -> None:
        """Restore cached device state from Domoticz.Configuration()."""
        if DEVICE_ID not in Devices:
            return
        
        configuration = Domoticz.Configuration()
        cached_state = configuration.get("device_state")
        if isinstance(cached_state, dict):
            for raw_unit, values in cached_state.items():
                try:
                    unit = int(raw_unit)
                except (TypeError, ValueError):
                    continue
                if unit not in Devices[DEVICE_ID].Units or not isinstance(values, dict):
                    continue
                n_value = int(values.get("nValue", 0) or 0)
                s_value = str(values.get("sValue", ""))
                unit_obj = Devices[DEVICE_ID].Units[unit]
                unit_obj.nValue = n_value
                unit_obj.sValue = s_value
                unit_obj.Update(Log=False)

     
    def update_cached_state(self, *, error: str) -> None:
        """Store current device state in Domoticz.Configuration() for persistence."""
        if DEVICE_ID not in Devices:
            return
        
        configuration = Domoticz.Configuration()
        configuration["device_state"] = {
            str(unit): {
                "nValue": int(Devices[DEVICE_ID].Units[unit].nValue),
                "sValue": str(Devices[DEVICE_ID].Units[unit].sValue),
            }
            for unit in Devices[DEVICE_ID].Units
        }
        configuration["last_error"] = error
        Domoticz.Configuration(configuration)

    def truncate_text(self, value: str, limit: int = 255) -> str:
        compact_value = " ".join(value.split())
        if len(compact_value) <= limit:
            return compact_value
        return compact_value[: limit - 3] + "..."

    def format_float(self, value: float | None, *, default: str = "0") -> str:
        if value is None:
            return default
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.1f}"


_plugin = BasePlugin()


def onStart() -> None:
    _plugin.onStart()


def onHeartbeat() -> None:
    _plugin.onHeartbeat()


def onStop() -> None:
    _plugin.onStop()
