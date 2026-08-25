"""The set of environments Chrome ships a distinct user agent for.

Since the User-Agent reduction that completed in Chrome 110, the desktop
platform token is *frozen*: every Windows install reports the same
``Windows NT 10.0; Win64; x64`` regardless of Windows 10 vs 11, x64 vs ARM64.
So there is exactly one desktop user agent per OS, not one per OS build. The
per-install detail that used to live in the User-Agent now lives in the
high-entropy client hints, which is why those are modelled separately here.

Chrome on iOS is a WKWebView wrapper rather than a Chromium content shell: it
uses Safari's UA shape with a ``CriOS`` product token, ships the full version
rather than a reduced one, and does not implement User-Agent Client Hints.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# content/common/user_agent.cc :: GetUnifiedPlatform
UNIFIED_PLATFORM = {
    "windows": "Windows NT 10.0; Win64; x64",
    "macos": "Macintosh; Intel Mac OS X 10_15_7",
    "linux": "X11; Linux x86_64",
    "chromeos": "X11; CrOS x86_64 14541.0.0",
    "android": "Linux; Android 10; K",
}

CHROMIUM_TEMPLATE = (
    "Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/{version}{mobile} Safari/537.36"
)
CRIOS_TEMPLATE = (
    "Mozilla/5.0 ({platform}) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "CriOS/{version} Mobile/15E148 Safari/604.1"
)


@dataclass(frozen=True)
class Environment:
    """One environment that Chrome reports a distinct User-Agent for."""

    id: str
    label: str
    #: Which Chrome Version History platform supplies this env's version.
    version_platform: str
    os: str
    form_factor: str
    engine: str = "blink"
    #: Frozen platform token, or an iOS template slot for CriOS environments.
    platform_token: str = ""
    mobile: bool = False
    #: Sec-CH-UA-Platform value; None for environments without client hints.
    ch_platform: str | None = None
    ch_form_factors: tuple[str, ...] = ()
    high_entropy: dict[str, str] = field(default_factory=dict)


def _desktop(env_id: str, label: str, version_platform: str, os_name: str,
             ch_platform: str, **high_entropy: str) -> Environment:
    return Environment(
        id=env_id,
        label=label,
        version_platform=version_platform,
        os=os_name,
        form_factor="desktop",
        platform_token=UNIFIED_PLATFORM[env_id],
        ch_platform=ch_platform,
        ch_form_factors=("Desktop",),
        high_entropy=high_entropy,
    )


ENVIRONMENTS: tuple[Environment, ...] = (
    _desktop(
        "windows", "Windows (x64)", "win64", "Windows", "Windows",
        arch="x86", bitness="64", model="", wow64="?0",
    ),
    _desktop(
        "macos", "macOS (Apple silicon)", "mac_arm64", "macOS", "macOS",
        arch="arm", bitness="64", model="", wow64="?0",
    ),
    _desktop(
        "linux", "Linux (x86_64)", "linux", "Linux", "Linux",
        arch="x86", bitness="64", model="", wow64="?0",
    ),
    _desktop(
        "chromeos", "ChromeOS (x86_64)", "chromeos", "ChromeOS", "Chrome OS",
        arch="x86", bitness="64", model="", wow64="?0",
    ),
    Environment(
        id="android-phone",
        label="Android phone",
        version_platform="android",
        os="Android",
        form_factor="phone",
        platform_token=UNIFIED_PLATFORM["android"],
        mobile=True,
        ch_platform="Android",
        ch_form_factors=("Mobile",),
        high_entropy={"arch": "", "bitness": "", "model": "K", "wow64": "?0"},
    ),
    Environment(
        id="android-tablet",
        label="Android tablet",
        version_platform="android",
        os="Android",
        form_factor="tablet",
        platform_token=UNIFIED_PLATFORM["android"],
        # Tablets do not run with the mobile UA switch, so both the " Mobile"
        # product suffix and the Sec-CH-UA-Mobile bit are off.
        mobile=False,
        ch_platform="Android",
        ch_form_factors=("Tablet",),
        high_entropy={"arch": "", "bitness": "", "model": "K", "wow64": "?0"},
    ),
    Environment(
        id="ios-phone",
        label="iPhone",
        version_platform="ios",
        os="iOS",
        form_factor="phone",
        engine="webkit",
        platform_token="iPhone; CPU iPhone OS {os_version} like Mac OS X",
        mobile=True,
        ch_platform=None,
    ),
    Environment(
        id="ios-tablet",
        label="iPad",
        version_platform="ios",
        os="iPadOS",
        form_factor="tablet",
        engine="webkit",
        platform_token="iPad; CPU OS {os_version} like Mac OS X",
        mobile=False,
        ch_platform=None,
    ),
)

BY_ID = {env.id: env for env in ENVIRONMENTS}
