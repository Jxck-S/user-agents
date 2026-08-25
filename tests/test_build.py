"""Shape and correctness checks for the generated documents."""

import datetime
import json
import re
import unittest
from pathlib import Path

from chrome_ua import build as build_mod
from chrome_ua.environments import BY_ID, ENVIRONMENTS
from chrome_ua.versions import Release

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((REPO_ROOT / "config.json").read_text())
DATA = REPO_ROOT / "data"

BLINK_UA = re.compile(
    r"^Mozilla/5\.0 \(.+\) AppleWebKit/537\.36 \(KHTML, like Gecko\) "
    r"Chrome/\d+\.0\.0\.0( Mobile)? Safari/537\.36$"
)
CRIOS_UA = re.compile(
    r"^Mozilla/5\.0 \(i(Phone|Pad); CPU (iPhone )?OS \d+_\d+(_\d+)? like Mac OS X\) "
    r"AppleWebKit/605\.1\.15 \(KHTML, like Gecko\) CriOS/[\d.]+ Mobile/15E148 "
    r"Safari/604\.1$"
)


def entry(env_id, version="151.0.7922.174"):
    return build_mod.build_entry(BY_ID[env_id], Release(version, 1.0), CONFIG)


class UserAgentShapeTest(unittest.TestCase):
    def test_every_environment_produces_a_wellformed_ua(self):
        for env in ENVIRONMENTS:
            with self.subTest(env=env.id):
                ua = entry(env.id)["user_agent"]
                pattern = CRIOS_UA if env.engine == "webkit" else BLINK_UA
                self.assertRegex(ua, pattern)

    def test_blink_ua_hides_the_build_number(self):
        ua = entry("windows")["user_agent"]
        self.assertIn("Chrome/151.0.0.0", ua)
        self.assertNotIn("7922", ua)

    def test_ios_ua_keeps_the_full_version(self):
        self.assertIn("CriOS/151.0.7922.174", entry("ios-phone")["user_agent"])

    def test_mobile_token_only_on_phones(self):
        self.assertIn(" Mobile Safari", entry("android-phone")["user_agent"])
        self.assertNotIn(" Mobile Safari", entry("android-tablet")["user_agent"])
        self.assertNotIn(" Mobile Safari", entry("windows")["user_agent"])

    def test_environment_ids_are_unique(self):
        ids = [env.id for env in ENVIRONMENTS]
        self.assertEqual(len(ids), len(set(ids)))


class ClientHintsTest(unittest.TestCase):
    def test_ios_has_no_client_hints(self):
        for env_id in ("ios-phone", "ios-tablet"):
            self.assertIsNone(entry(env_id)["client_hints"], env_id)

    def test_mobile_bit_tracks_the_ua_mobile_token(self):
        for env in ENVIRONMENTS:
            hints = entry(env.id)["client_hints"]
            if hints is None:
                continue
            expected = "?1" if env.mobile else "?0"
            self.assertEqual(hints["low_entropy"]["Sec-CH-UA-Mobile"], expected, env.id)

    def test_full_version_list_carries_the_exact_build(self):
        hints = entry("windows")["client_hints"]["high_entropy"]
        self.assertIn("151.0.7922.174", hints["Sec-CH-UA-Full-Version-List"])


class PublishedDataTest(unittest.TestCase):
    """Guards the committed JSON, so a bad generated file fails CI too."""

    def test_committed_files_are_valid(self):
        for name in ("user-agents.json", "latest.json"):
            path = DATA / name
            with self.subTest(file=name):
                self.assertTrue(path.exists(), f"{name} has not been generated")
                document = json.loads(path.read_text())
                self.assertEqual(document["schema_version"], build_mod.SCHEMA_VERSION)

    def test_stable_channel_covers_every_environment(self):
        document = json.loads((DATA / "user-agents.json").read_text())
        published = set(document["channels"]["stable"]["environments"])
        self.assertEqual(published, {env.id for env in ENVIRONMENTS})

    def test_latest_matches_the_full_document(self):
        full = json.loads((DATA / "user-agents.json").read_text())
        latest = json.loads((DATA / "latest.json").read_text())
        for env_id, ua in latest["user_agents"].items():
            expected = full["channels"]["stable"]["environments"][env_id]["user_agent"]
            self.assertEqual(ua, expected, env_id)


if __name__ == "__main__":
    unittest.main()


class OsVersionFreshnessTest(unittest.TestCase):
    """The hand-maintained OS versions are the one thing that can rot quietly."""

    def test_verified_date_is_present_and_wellformed(self):
        self.assertIn("os_versions_verified", CONFIG)
        datetime.date.fromisoformat(CONFIG["os_versions_verified"])

    def test_verified_date_is_not_in_the_future(self):
        verified = datetime.date.fromisoformat(CONFIG["os_versions_verified"])
        self.assertLessEqual(verified, datetime.datetime.now(datetime.timezone.utc).date())

    def test_every_client_hint_environment_has_an_os_version(self):
        for env in ENVIRONMENTS:
            if env.ch_platform is None:
                continue
            self.assertIn(env.id, CONFIG["os_versions"], env.id)

    def test_linux_reports_an_empty_platform_version(self):
        # content/common/user_agent.cc returns an empty string on Linux.
        self.assertEqual(CONFIG["os_versions"]["linux"], "")
        hints = entry("linux")["client_hints"]["high_entropy"]
        self.assertEqual(hints["Sec-CH-UA-Platform-Version"], '""')

    def test_age_is_measured_from_the_verified_date(self):
        config = {"os_versions_verified": "2026-01-01"}
        age = build_mod.os_versions_age_days(config, today=datetime.date(2026, 7, 1))
        self.assertEqual(age, 181)

    def test_age_is_none_when_undated(self):
        self.assertIsNone(build_mod.os_versions_age_days({}))
