"""Fetch current Chrome versions from Google's Chrome Version History API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

API_ROOT = "https://versionhistory.googleapis.com/v1/chrome"
RELEASES_PATH = "{root}/platforms/{platform}/channels/{channel}/versions/all/releases"

CHANNELS = ("stable", "beta", "dev", "canary")


class VersionLookupError(RuntimeError):
    """Raised when the upstream API returns nothing usable for a platform."""


@dataclass(frozen=True)
class Release:
    version: str
    fraction: float

    @property
    def major(self) -> int:
        return int(self.version.split(".", 1)[0])

    def sort_key(self) -> tuple[int, ...]:
        return tuple(int(part) for part in self.version.split("."))


def _get(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_releases(platform: str, channel: str, timeout: float = 30.0) -> list[Release]:
    """Return the releases currently being served for a platform and channel."""
    query = urllib.parse.urlencode(
        {"filter": "endtime=none", "order_by": "version desc", "page_size": 20}
    )
    url = f"{RELEASES_PATH.format(root=API_ROOT, platform=platform, channel=channel)}?{query}"
    try:
        payload = _get(url, timeout)
    except urllib.error.HTTPError as exc:
        raise VersionLookupError(f"{platform}/{channel}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise VersionLookupError(f"{platform}/{channel}: {exc.reason}") from exc

    releases = [
        Release(version=item["version"], fraction=float(item.get("fraction", 0.0)))
        for item in payload.get("releases", [])
        if "version" in item
    ]
    if not releases:
        raise VersionLookupError(f"{platform}/{channel}: no releases currently serving")
    return releases


def pick(releases: list[Release], prefer: str = "rollout") -> Release:
    """Choose the release to build user agents from.

    ``rollout`` (the default) picks the build the largest share of users are
    actually running, which is what a realistic user agent should claim. During
    a staged rollout that is the outgoing version, not the newest one.
    ``newest`` picks the highest version number regardless of rollout share.
    """
    if prefer == "newest":
        return max(releases, key=Release.sort_key)
    if prefer != "rollout":
        raise ValueError(f"unknown preference: {prefer!r}")
    # A version can appear once per rollout step. Later steps supersede earlier
    # ones rather than adding to them, so a version's share is the largest of
    # its steps, never their sum.
    totals: dict[str, float] = {}
    for release in releases:
        totals[release.version] = max(totals.get(release.version, 0.0), release.fraction)
    version, fraction = max(
        totals.items(), key=lambda item: (item[1], Release(item[0], 0.0).sort_key())
    )
    return Release(version=version, fraction=round(fraction, 6))
