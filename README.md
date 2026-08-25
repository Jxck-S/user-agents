# user-agents

Accurate Chrome user-agent strings and User-Agent Client Hints as JSON, regenerated
automatically from upstream Chrome releases.

There is no scraping and no hand-copied UA list. Versions come from Google's Chrome
Version History API; the string shapes and the `Sec-CH-UA` brand lists are reproduced
from Chromium's own source, so the output matches what a real Chrome build of that
version sends.

## Use it

The files under `data/` are the product. Fetch them directly:

```
https://raw.githubusercontent.com/Jxck-S/user-agents/main/data/latest.json
https://raw.githubusercontent.com/Jxck-S/user-agents/main/data/user-agents.json
```

```python
import urllib.request, json

URL = "https://raw.githubusercontent.com/Jxck-S/user-agents/main/data/latest.json"
with urllib.request.urlopen(URL) as r:
    agents = json.load(r)["user_agents"]

headers = {"User-Agent": agents["windows"]}
```

```js
const res = await fetch("https://raw.githubusercontent.com/Jxck-S/user-agents/main/data/latest.json");
const { user_agents } = await res.json();
const ua = user_agents["windows"];
```

## Files

| File | Contents |
| --- | --- |
| `data/latest.json` | Flat `environment id → user agent` map for the stable channel. Use this unless you need more. |
| `data/user-agents.json` | Every channel (stable, beta, dev, canary), every environment, with client hints, exact build numbers, and rollout share. |

`latest.json` looks like this:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-25T00:00:00Z",
  "channel": "stable",
  "versions": { "windows": "151.0.7922.174" },
  "user_agents": {
    "windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
  }
}
```

Each environment in `user-agents.json` carries the reduced UA plus the headers that
travel with it:

```json
{
  "id": "windows",
  "os": "Windows",
  "form_factor": "desktop",
  "chrome_version": "151.0.7922.174",
  "chrome_major": 151,
  "rollout_fraction": 1.0,
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
  "client_hints": {
    "low_entropy": {
      "Sec-CH-UA": "\"Not=A?Brand\";v=\"99\", \"Google Chrome\";v=\"151\", \"Chromium\";v=\"151\"",
      "Sec-CH-UA-Mobile": "?0",
      "Sec-CH-UA-Platform": "\"Windows\""
    },
    "high_entropy": { "Sec-CH-UA-Full-Version-List": "...", "...": "..." }
  }
}
```

## Environments

One entry per environment Chrome actually reports differently — eight in total:

| id | OS | Form factor | Notes |
| --- | --- | --- | --- |
| `windows` | Windows | desktop | |
| `macos` | macOS | desktop | |
| `linux` | Linux | desktop | |
| `chromeos` | ChromeOS | desktop | |
| `android-phone` | Android | phone | carries the ` Mobile` product token |
| `android-tablet` | Android | tablet | no ` Mobile` token, `Sec-CH-UA-Mobile: ?0` |
| `ios-phone` | iOS | phone | `CriOS`, no client hints |
| `ios-tablet` | iPadOS | tablet | `CriOS`, no client hints |

### Why there is only one Windows entry

Chrome's [User-Agent reduction](https://developer.chrome.com/docs/privacy-security/user-agent-reduction),
completed in Chrome 110, froze the desktop platform token. Every Windows install now
reports `Windows NT 10.0; Win64; x64` — Windows 10 and Windows 11, x64 and ARM64, all
identical. Publishing separate `windows-11-arm64` and `windows-10-x64` user agents would
mean publishing the same string several times under different names, or publishing
strings no current Chrome sends.

The detail that used to live in the User-Agent moved to the high-entropy client hints,
which is where this repo puts it: `Sec-CH-UA-Platform-Version` distinguishes Windows 11
(`15.0.0`) from Windows 10 (`10.0.0`), and `Sec-CH-UA-Arch` distinguishes x86 from ARM.
Android is frozen the same way — device model reported as `K`, OS version as `10`,
regardless of the real device.

Chrome on iOS is the exception: it wraps WKWebView rather than shipping Blink, so it is
not UA-reduced. Those entries use Safari's shape with a `CriOS` token, report the full
build number, and have no client hints, because Chrome on iOS does not implement them.

## Which build gets reported

Chrome stable rolls out in stages, so more than one version is in the wild at once. By
default the generator picks the build the **largest share of users are running**, which
is what a realistic user agent should claim — during a staged rollout that is the
outgoing version, not the newest one. `--prefer newest` picks the highest released
version instead. `rollout_fraction` records the share the chosen build was serving.

## Updating

`.github/workflows/update.yml` runs every six hours, regenerates the data, runs the test
suite against it, and commits only when Chrome has actually moved. Quiet runs leave the
files and the git history untouched, so the commit log is a log of Chrome releases.

## Running it yourself

No dependencies — standard library only, Python 3.10+.

```sh
python -m chrome_ua                      # regenerate data/
python -m chrome_ua --print              # write to stdout instead
python -m chrome_ua --check              # exit 1 if data/ is stale
python -m chrome_ua --channels stable    # limit the channels fetched
python -m chrome_ua --prefer newest      # claim the newest build
python -m unittest discover -s tests -t .
```

## What is hand-maintained

Almost nothing, and it is all in `config.json`: the host OS versions reported through
`Sec-CH-UA-Platform-Version`, and the iOS version used in the `CriOS` strings. Chrome's
release feed does not carry these, so they cannot be derived from upstream the way
everything else here is.

Because they cannot update themselves, they are the one thing in this repo that can rot
quietly. So they are dated. `config.json` carries `os_versions_verified`, the generator
warns when that date is more than 180 days old, and the date is republished in the output
so consumers can judge how much to trust those fields:

```
warning: the host OS versions in config.json were last reviewed 2428 days ago; they do
not update themselves, so Sec-CH-UA-Platform-Version and the iOS user agents may be out
of date
```

Bump the date whenever you review the values. Note that only `ios_version` reaches the
user-agent string; the rest affect high-entropy client hints, which are sent only when a
server explicitly requests them.

### Sec-CH-UA-Platform-Version on Windows

Worth knowing before you edit it: on Windows this is **not** the Windows version. Chrome
reports the UniversalApiContract version (`GetUniversalApiContractVersion` in
`user_agent_utils.cc`):

| Windows release | Reported |
| --- | --- |
| Windows 10 1507 … 22H2 | `1.0.0` … `10.0.0` |
| Windows 11 21H2 | `14.0.0` |
| Windows 11 22H2 / 23H2 | `15.0.0` |
| Windows 11 24H2+ | higher; Chromium caps its own fallback at `19` |

Anything at or above `13.0.0` means Windows 11. Set `10.0.0` to present as Windows 10.
On Linux the value is an empty string, which is what Chromium itself returns.

## Provenance

| Output | Source |
| --- | --- |
| Chrome versions per platform and channel | [Chrome Version History API](https://developer.chrome.com/docs/web-platform/version-history/reference) |
| Frozen platform tokens | Chromium `components/embedder_support/user_agent_utils.cc`, `GetUnifiedPlatform` |
| `Sec-CH-UA` brand lists and GREASE | Chromium `user_agent_utils.cc`, `GenerateBrandVersionList` / `GetRandomOrder` |
| UA string templates | Chromium `BuildUserAgentFromOSAndProduct` |

The GREASE port is checked in `tests/test_grease.py` against headers captured from real
Chrome 120 and 131 builds, so a regression in the algorithm fails CI rather than quietly
shipping plausible-looking but wrong headers.

## License

MIT.
