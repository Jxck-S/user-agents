"""Assemble the published user-agent JSON documents."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from . import grease
from .environments import CHROMIUM_TEMPLATE, CRIOS_TEMPLATE, ENVIRONMENTS, Environment
from .versions import CHANNELS, Release, VersionLookupError, fetch_releases, pick

SCHEMA_VERSION = 1

#: How long the hand-maintained OS versions in config.json may go unreviewed
#: before the generator starts complaining about them.
STALE_AFTER_DAYS = 180
SOURCE = {
    "name": "Chrome Version History API",
    "endpoint": "https://versionhistory.googleapis.com/v1/chrome/platforms/"
                "{platform}/channels/{channel}/versions/all/releases",
    "docs": "https://developer.chrome.com/docs/web-platform/version-history/reference",
}
NOTES = [
    "Desktop user agents are frozen by Chrome's User-Agent reduction: every "
    "Windows install reports 'Windows NT 10.0; Win64; x64' whatever the actual "
    "Windows version or CPU architecture, so there is one desktop user agent "
    "per OS rather than one per OS build.",
    "Blink user agents report the major version with the remaining components "
    "zeroed (Chrome/151.0.0.0). The precise build is available only through "
    "Sec-CH-UA-Full-Version-List, which is included here.",
    "Chrome on iOS wraps WKWebView: it uses Safari's user agent shape with a "
    "CriOS product token, reports its full version, and does not implement "
    "User-Agent Client Hints, so those entries carry no client_hints.",
    "Sec-CH-UA brand lists are reproduced with Chromium's own GREASE algorithm, "
    "so they match byte-for-byte what a real build of that version sends.",
    "On Windows, Sec-CH-UA-Platform-Version reports the UniversalApiContract "
    "version rather than the Windows version; anything at or above 13.0.0 means "
    "Windows 11. See config.json for the mapping.",
    "os_versions_verified is the date the hand-maintained host OS versions were "
    "last reviewed. Chrome's release feed does not carry them, so unlike "
    "everything else here they do not update themselves.",
]


def os_versions_age_days(config: dict, today: _dt.date | None = None) -> int | None:
    """Days since the hand-maintained OS versions were last reviewed."""
    stamp = config.get("os_versions_verified")
    if not stamp:
        return None
    verified = _dt.date.fromisoformat(stamp)
    return ((today or _dt.datetime.now(_dt.timezone.utc).date()) - verified).days


def reduced_version(version: str) -> str:
    """Return the minor/build/patch-zeroed version Blink puts in the UA."""
    return f"{version.split('.', 1)[0]}.0.0.0"


def user_agent(env: Environment, version: str, ios_version: str) -> str:
    if env.engine == "webkit":
        platform = env.platform_token.format(os_version=ios_version.replace(".", "_"))
        return CRIOS_TEMPLATE.format(platform=platform, version=version)
    return CHROMIUM_TEMPLATE.format(
        platform=env.platform_token,
        version=reduced_version(version),
        mobile=" Mobile" if env.mobile else "",
    )


def client_hints(env: Environment, version: str, os_version: str) -> dict | None:
    """Build the client-hint headers a real Chrome build would send."""
    if env.ch_platform is None:
        return None
    major = int(version.split(".", 1)[0])
    return {
        "low_entropy": {
            "Sec-CH-UA": grease.serialize(grease.brand_list(major)),
            "Sec-CH-UA-Mobile": "?1" if env.mobile else "?0",
            "Sec-CH-UA-Platform": f'"{env.ch_platform}"',
        },
        "high_entropy": {
            "Sec-CH-UA-Arch": f'"{env.high_entropy["arch"]}"',
            "Sec-CH-UA-Bitness": f'"{env.high_entropy["bitness"]}"',
            "Sec-CH-UA-Model": f'"{env.high_entropy["model"]}"',
            "Sec-CH-UA-Platform-Version": f'"{os_version}"',
            "Sec-CH-UA-Full-Version-List": grease.serialize(
                grease.brand_list(major, full_version=version)
            ),
            "Sec-CH-UA-Form-Factors": ", ".join(
                f'"{factor}"' for factor in env.ch_form_factors
            ),
            "Sec-CH-UA-WoW64": env.high_entropy["wow64"],
        },
    }


def build_entry(env: Environment, release: Release, config: dict) -> dict:
    ios_version = config["ios_version"]
    os_version = (
        ios_version if env.engine == "webkit" else config["os_versions"].get(env.id, "")
    )
    return {
        "id": env.id,
        "label": env.label,
        "os": env.os,
        "os_version": os_version,
        "form_factor": env.form_factor,
        "engine": env.engine,
        "chrome_version": release.version,
        "chrome_major": release.major,
        "rollout_fraction": release.fraction,
        "user_agent": user_agent(env, release.version, ios_version),
        "client_hints": client_hints(env, release.version, os_version),
    }


def build_document(config: dict, channels=CHANNELS, prefer: str = "rollout",
          timeout: float = 30.0) -> tuple[dict, list[str]]:
    """Build the full document. Returns the document and any per-env warnings."""
    warnings: list[str] = []
    channel_docs: dict[str, dict] = {}
    cache: dict[tuple[str, str], Release] = {}

    for channel in channels:
        entries: dict[str, dict] = {}
        for env in ENVIRONMENTS:
            key = (env.version_platform, channel)
            if key not in cache:
                try:
                    cache[key] = pick(
                        fetch_releases(env.version_platform, channel, timeout), prefer
                    )
                except VersionLookupError as exc:
                    warnings.append(str(exc))
                    continue
            entries[env.id] = build_entry(env, cache[key], config)
        if entries:
            channel_docs[channel] = {
                "versions": {
                    env_id: entry["chrome_version"] for env_id, entry in entries.items()
                },
                "environments": entries,
            }

    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version_preference": prefer,
        "os_versions_verified": config.get("os_versions_verified"),
        "source": SOURCE,
        "notes": NOTES,
        "channels": channel_docs,
    }
    return document, warnings


def latest_document(document: dict, channel: str = "stable") -> dict:
    """A flat channel-specific view: environment id to user agent string."""
    entries = document["channels"][channel]["environments"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": document["generated_at"],
        "channel": channel,
        "versions": document["channels"][channel]["versions"],
        "user_agents": {env_id: entry["user_agent"] for env_id, entry in entries.items()},
    }


def dump(document: dict, path: Path) -> bool:
    """Write ``document`` to ``path``. Returns True if the content changed.

    ``generated_at`` is ignored when comparing so a scheduled run that finds no
    new Chrome release leaves the file, and the git history, untouched.
    """
    text = json.dumps(document, indent=2, sort_keys=False) + "\n"
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except json.JSONDecodeError:
            old = None
        if old is not None:
            comparable_old = {k: v for k, v in old.items() if k != "generated_at"}
            comparable_new = {k: v for k, v in document.items() if k != "generated_at"}
            if comparable_old == comparable_new:
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True
