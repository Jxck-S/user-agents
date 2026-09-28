"""Version selection, exercised without touching the network."""

import unittest
import urllib.error
from unittest import mock

from chrome_ua import versions
from chrome_ua.versions import Release, VersionLookupError, fetch_releases, pick


def http_error(code):
    return urllib.error.HTTPError("url", code, "error", {}, None)


class FetchRetryTest(unittest.TestCase):
    PAYLOAD = {"releases": [{"version": "152.0.7977.113", "fraction": 1.0}]}

    def fetch(self, side_effect):
        with mock.patch.object(versions, "_get", side_effect=side_effect) as get, \
                mock.patch.object(versions.time, "sleep"):
            try:
                return fetch_releases("chromeos", "stable"), get.call_count
            except VersionLookupError as exc:
                return exc, get.call_count

    def test_server_errors_are_retried(self):
        result, calls = self.fetch([http_error(500), self.PAYLOAD])
        self.assertEqual(result, [Release("152.0.7977.113", 1.0)])
        self.assertEqual(calls, 2)

    def test_read_timeouts_are_retried(self):
        result, calls = self.fetch([TimeoutError("timed out"), self.PAYLOAD])
        self.assertEqual(result, [Release("152.0.7977.113", 1.0)])
        self.assertEqual(calls, 2)

    def test_persistent_failure_becomes_a_lookup_error(self):
        result, calls = self.fetch(TimeoutError("timed out"))
        self.assertIsInstance(result, VersionLookupError)
        self.assertEqual(calls, 3)

    def test_client_errors_are_not_retried(self):
        result, calls = self.fetch(http_error(404))
        self.assertIsInstance(result, VersionLookupError)
        self.assertEqual(calls, 1)


class PickTest(unittest.TestCase):
    def setUp(self):
        # A staged rollout: the new version is out to a sliver of users while
        # the outgoing one still serves nearly everybody.
        self.releases = [
            Release("152.0.7977.54", 0.005),
            Release("151.0.7922.174", 0.99),
            Release("151.0.7922.174", 1.0),
        ]

    def test_rollout_prefers_what_most_users_run(self):
        self.assertEqual(pick(self.releases).version, "151.0.7922.174")

    def test_rollout_fraction_never_exceeds_one(self):
        # The same version listed under several rollout steps must not have its
        # shares added together.
        self.assertLessEqual(pick(self.releases).fraction, 1.0)

    def test_newest_prefers_the_highest_version(self):
        self.assertEqual(pick(self.releases, "newest").version, "152.0.7977.54")

    def test_version_sorting_is_numeric_not_lexicographic(self):
        releases = [Release("99.0.1.9", 1.0), Release("100.0.1.0", 1.0)]
        self.assertEqual(pick(releases, "newest").version, "100.0.1.0")

    def test_unknown_preference_is_rejected(self):
        with self.assertRaises(ValueError):
            pick(self.releases, "whatever")


if __name__ == "__main__":
    unittest.main()
