"""Command line entry point: regenerate the JSON in data/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import STALE_AFTER_DAYS, build_document, dump, latest_document, os_versions_age_days
from .versions import CHANNELS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.json"
DEFAULT_OUT = REPO_ROOT / "data"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="chrome_ua",
        description="Generate user-agent JSON from upstream Chrome releases.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="directory to write the JSON files into")
    parser.add_argument("--channels", nargs="+", default=list(CHANNELS),
                        choices=list(CHANNELS))
    parser.add_argument("--prefer", choices=("rollout", "newest"), default="rollout",
                        help="'rollout' claims the build most users are running; "
                             "'newest' claims the highest released version")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the generated JSON differs from what is "
                             "committed, without writing anything")
    parser.add_argument("--print", dest="to_stdout", action="store_true",
                        help="write the full document to stdout instead of to files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = json.loads(args.config.read_text())

    age = os_versions_age_days(config)
    if age is None:
        print("warning: config.json has no os_versions_verified date", file=sys.stderr)
    elif age > STALE_AFTER_DAYS:
        print(
            f"warning: the host OS versions in config.json were last reviewed "
            f"{age} days ago; they do not update themselves, so Sec-CH-UA-"
            f"Platform-Version and the iOS user agents may be out of date",
            file=sys.stderr,
        )

    document, warnings = build_document(
        config, channels=args.channels, prefer=args.prefer, timeout=args.timeout
    )
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    if not document["channels"]:
        print("error: no channel data could be fetched", file=sys.stderr)
        return 2

    if args.to_stdout:
        json.dump(document, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    targets = [(document, args.out / "user-agents.json")]
    if "stable" in document["channels"]:
        targets.append((latest_document(document), args.out / "latest.json"))

    if args.check:
        stale = [path.name for doc, path in targets if _differs(doc, path)]
        if stale:
            print(f"out of date: {', '.join(stale)}", file=sys.stderr)
            return 1
        print("up to date")
        return 0

    changed = [path.name for doc, path in targets if dump(doc, path)]
    print(f"updated: {', '.join(changed)}" if changed else "no changes")
    return 0


def _differs(document: dict, path: Path) -> bool:
    if not path.exists():
        return True
    try:
        old = json.loads(path.read_text())
    except json.JSONDecodeError:
        return True
    drop = lambda d: {k: v for k, v in d.items() if k != "generated_at"}
    return drop(old) != drop(document)
