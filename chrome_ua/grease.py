"""Chrome's GREASE brand-list algorithm for Sec-CH-UA headers.

This is a faithful port of Chromium's ``GenerateBrandVersionList`` from
``components/embedder_support/user_agent_utils.cc``. The brand list is a
deterministic function of the Chrome major version, so given a version we can
reproduce byte-for-byte what a real Chrome build sends.
"""

from __future__ import annotations

# components/embedder_support/user_agent_utils.cc :: GetGreasedUserAgentBrandVersion
GREASY_CHARS = (" ", "(", ":", "-", ".", "/", ")", ";", "=", "?", "_")
GREASED_VERSIONS = ("8", "99", "24")

# components/embedder_support/user_agent_utils.cc :: GetRandomOrder
ORDERS_3 = (
    (0, 1, 2),
    (0, 2, 1),
    (1, 0, 2),
    (1, 2, 0),
    (2, 0, 1),
    (2, 1, 0),
)


def greasy_brand(major: int) -> str:
    """Return the GREASE brand name Chrome ``major`` advertises."""
    return "Not{}A{}Brand".format(
        GREASY_CHARS[major % len(GREASY_CHARS)],
        GREASY_CHARS[(major + 1) % len(GREASY_CHARS)],
    )


def greasy_version(major: int, full: bool = False) -> str:
    """Return the arbitrarily low version paired with the GREASE brand."""
    version = GREASED_VERSIONS[major % len(GREASED_VERSIONS)]
    # The greased versions are all single-component, so the full-version form
    # is the significant version padded out to four components.
    return f"{version}.0.0.0" if full else version


def brand_list(major: int, full_version: str | None = None) -> list[dict[str, str]]:
    """Build the shuffled brand/version list for a Chrome major version.

    Passing ``full_version`` produces the ``Sec-CH-UA-Full-Version-List`` form;
    omitting it produces the low-entropy ``Sec-CH-UA`` form.
    """
    full = full_version is not None
    version = full_version if full else str(major)
    brands = [
        {"brand": greasy_brand(major), "version": greasy_version(major, full)},
        {"brand": "Chromium", "version": version},
        {"brand": "Google Chrome", "version": version},
    ]

    # ShuffleBrandList: shuffled[order[i]] = brands[i]
    order = ORDERS_3[major % len(ORDERS_3)]
    shuffled: list[dict[str, str]] = [{} for _ in brands]
    for i, position in enumerate(order):
        shuffled[position] = brands[i]
    return shuffled


def serialize(brands: list[dict[str, str]]) -> str:
    """Render a brand list as an HTTP structured-header value."""
    return ", ".join(f'"{b["brand"]}";v="{b["version"]}"' for b in brands)
