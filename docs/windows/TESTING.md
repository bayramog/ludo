# Portable test execution (F1-06 / #11)

## Current dev adaptation

Base: `f7abe54e8fbe428aab0eaf5b0c0bfd06fff071c8` (#6 paths on upstream
`e3705259`), adapted from the reviewed #249 infrastructure at `29e4ec3`.
The current manifest contains **86 engine files** (74 selected on Windows,
12 explicitly excluded) and **24 backend files / 214 cases** (23 files / 213
cases selected on Windows). Linux runs the complete inventory. These are file,
unittest-case and custom-harness counts, not interchangeable assertion totals.

Upstream `process-locks.yml` is retained byte-for-byte alongside the new
`portable-tests.yml` matrix and complete Linux CI. No engine/backend product code
is changed by this layer. Cemu's newer AppImage adoption and exact chmod assertions
remain tested; only the two POSIX permission checks have a separate Linux file.

The native matrix tests fixture data on hosted Windows Server and Ubuntu with
Python 3.11 and 3.13. This is not Windows 11 desktop/handheld, installer/portable
ZIP, emulator, or real RomM-account acceptance. The existing #249 PR and its
historical branch are separate from this `feat/windows-portable-tests-dev` layer.

## Commands

Install the editable engine and backend test dependencies into the chosen Python:

```sh
python -m pip install -e engine
python -m pip install -e "app[test]"
python -m unittest discover -s scripts/tests -v
python engine/tests/run.py
python engine/tests/run.py keys eden
python scripts/test_backend.py
```

The engine runner uses exactly `sys.executable`, invokes every standalone file
in its own process with `engine/` as cwd, and uses OR-ed literal filename
substrings. `LUDO_TEST_PYTHON=/path/to/python engine/tests/run.sh keys eden` keeps
the existing Bash interpreter/dependency selection. With already installed deps
it works offline; if none of the candidate interpreters has dependencies, Bash
reuses or creates `engine/.venv-tests` as before. The Python entrypoint never
invokes pip or substitutes an interpreter. Empty selection/configuration errors
exit 2, child/test/zero-test/skip failures exit 1, all selected files passing exits
0. The default per-script timeout is 300 seconds (`--timeout` overrides it).

`test_activity_actions.py` formerly only defined pytest functions and did no
work under the standalone runner. Its unittest entrypoint now executes both
contracts. Existing engine `ok` lines, unittest cases and completion markers are
reported separately: they are not interchangeable assertion counts. A silent
zero-exit script fails. Standalone `skip`/`SKIP` lines also fail the gate (including a missing 7z binary
in the Linux Cemu fixture). Backend runs real pytest, parses its private JUnit
counts and rejects zero tests or unexpected skips. A private pytest plugin also
records collected/executed counts by each item's resolved file path, so an empty
selected file cannot borrow a passing sibling's tests. Parametrized, class and
unittest cases retain normal single-process pytest collection. Actual test
errors/skips take precedence over the per-file zero-test diagnosis.

## Platform accounting

`scripts/test-platforms.json` accounts for every engine/backend `test_*.py`,
including nested files. Adding, deleting or classifying a file twice fails
validation. A Windows exclusion requires a file name, concrete reason and fork
issue URL. Every exclusion is printed and included in the structural report;
selecting only excluded files is an error. `--native` applies those exclusions
on Windows; Linux always executes every file. Without `--native`, even excluded
files execute, which supports remediation/probing. This manifest does not
suppress individual unexpected skips or turn failures into passes.

The separate Linux CI retains the complete engine/backend suites, built-dist
browser/host/render tests with the existing render-skip guard, and Decky
typecheck. These browser tests are Linux-hosted; Windows packaged UI acceptance
remains in [F5-04](https://github.com/bayramog/ludo/issues/243).

The runner's three Bash compatibility/bootstrap tests are POSIX-only and
visibly skipped on Windows: Windows invokes Python directly. Its other thirty-one
negative/execution and fixture contracts execute on both OSes. Tracking: [F1-06](https://github.com/bayramog/ludo/issues/11).

## Isolation and failure evidence

Every engine child gets a fresh HOME/USERPROFILE, APPDATA/LOCALAPPDATA,
XDG roots and temporary directory. Backend has an isolated suite profile and
its existing conftest/per-test fixtures. Child environments retain only
OS/interpreter essentials, never caller tokens, application overrides or proxy
credentials. PYTHONPATH points at this checkout's engine/app. Tests use synthetic
fixtures or loopback servers; CI does not receive RomM credentials or libraries.

`--report-dir <new-directory>` writes a structured `summary.json` (maximum
256 KiB). Reusing a report directory is rejected to prevent stale evidence.
The report records commit, OS/Python versions, selection, exclusions, per-file
status/counts (including per-backend-file collection/execution), exit codes,
timeouts, elapsed time and at most twelve traceback
file/line locations per failed group. It does not contain raw output, exception
messages, environment, JUnit XML, settings, keys or profile contents. Raw child
output is bounded to its last 64 KiB on failure in the job console. Failure
artifact uploads select only these JSON summaries and expire after seven days.

Negative contracts exercise actual subprocesses, silent/empty/unittest-zero
runs, failing exit codes, unexpected skips, timeout/spawn failures, missing
JUnit, manifest drift and bounded evidence that excludes a synthetic secret.

## Measured Windows scope on current dev

[The initial full native probe](https://github.com/bayramog/ludo/actions/runs/45138655061)
at `30e342e` selected all 83 then-existing engine files and all 214 backend cases
on **both** Windows Python versions. It found 19 failing engine files and one
failing backend transaction. Linux passed all 83 files / 214 cases; the separate
[complete Linux CI](https://github.com/bayramog/ludo/actions/runs/45138654672)
also passed built desktop tests/render guard and Decky typecheck.

Windows fixture failures were fixed without changing product behavior:

- Cemu sync, Eden users, profiles, Cemu install discovery and legacy Switch-key
  receipts now isolate HOME, USERPROFILE, APPDATA and LOCALAPPDATA together.
  Profile assertions use the specified native state root; Windows RetroArch
  overlay fixtures use a synthetic portable exe/config, while Linux retains its
  original Flatpak layout.
- Auto-sync tests retain real owner/contender/reacquisition checks. Windows
  denies reads through another handle while byte zero is locked; the unchanged
  owner metadata is now checked after release, with cleanup on all paths.
- BIOS symlink topology and PCEE2 card tests passed Windows symlink creation but
  expected Unix separators. Native relative-path expectations retain the real
  filesystem traversal, deduplication, depth and loop checks on both OSes.
- The 27 Cemu discovery/XDG audio checks that passed Windows stay selected in
  `test_cemu_standalone_linux.py`. These synthetic Flatpak/AppImage fixtures and
  argv contracts do not establish that either runtime executes on Windows.
- One portable Switch-mod path-conformance case moved to
  `test_switch_mod_paths.py`; all 23 fcntl-backed transaction cases remain on
  Linux. Only the one actual backend install/remove case moved to
  `test_mod_packages_transactions.py`; its other six backend cases still run on
  Windows. Import-time backend initialization also makes the filtered mod group
  independent of other files' collection order.

[The second native run](https://github.com/bayramog/ludo/actions/runs/45140153657)
at `7aa0f0a` passed all 213 selected backend cases and 73/74 selected engine
files on both Windows Python versions. The remaining profile case demonstrated
that `_same_path_value` only matches Unix `~/` suffixes, not Windows `~\` state
paths. The other 21 profile/store/overlay cases remain selected; the original
abbreviated-path case is preserved in `test_profiles_tilde_restore.py`
on Linux, pending the launcher/config normalization work. This is a measured
product boundary, not proof of actual RetroArch Windows save-on-exit spelling.

No upstream test/check label was discarded. The inventory grew by three engine
files and one backend file through these splits; full Linux backend case count
remains 214. #6's `test_windows_paths.py` and `test_path_fixture.py` stay selected.
The upstream `test_appimage_exec_bit.py` and `test_retroarch_process_detect.py`
passed the actual Windows probe and remain selected.

| Windows exclusion | Measured contract / follow-up |
| --- | --- |
| `test_bios_folder.py` | Flatpak config and first-launch discovery intentionally differ on Windows; 12 actual failures. [#9](https://github.com/bayramog/ludo/issues/9). |
| `test_bios_readiness_sigil.py` | Real disc serial/region priority needs native Sigil. Portable readiness/fallback and symlink checks run separately. [#8](https://github.com/bayramog/ludo/issues/8). |
| `test_cemu_appimage_permissions.py` | Exact POSIX owner-executable-bit assertion fails Windows; preserved on Linux. Other Cemu discovery/audio/argv contracts run on both. [#16](https://github.com/bayramog/ludo/issues/16). |
| `test_dreamcast_sync.py` | Real product-number-derived VMU sync/restore needs Sigil; stubbing it would remove the identity contract. [#8](https://github.com/bayramog/ludo/issues/8). |
| `test_emulator_saves_process.py` | Real POSIX shell executable, `/proc` identity, zombie/SIGTERM integration. Windows probe reports WinError 193. [#10](https://github.com/bayramog/ludo/issues/10). |
| `test_launch_core_dir.py` | Actual drive-prefix loss in `:/` normalization causes redundant core overrides; also includes Linux lib64 discovery. [#16](https://github.com/bayramog/ludo/issues/16). |
| `test_play_sessions_linux_boot.py` | Actual `/proc/sys/kernel/random/boot_id` evidence; synthetic recovery/unknown-boot scenarios run on both. [#10](https://github.com/bayramog/ludo/issues/10). |
| `test_profiles_tilde_restore.py` | Native `~\` state paths are not recognized by overlay restoration. All other 21 profile/store/overlay cases remain selected. [#16](https://github.com/bayramog/ludo/issues/16). |
| `test_switch_content_sigil.py` | Bundled library exists but does not load on Windows; 88 portable synthetic-container/install/ranking checks remain selected. [#8](https://github.com/bayramog/ludo/issues/8). |
| `test_switch_mods.py` | 23 real mod install/recovery/removal cases require the lazy `fcntl` transaction lock. Path conformance and missing-fcntl import contracts run on both. [#7](https://github.com/bayramog/ludo/issues/7). |
| `test_switch_nsz.py` | Actual compressed-container round trips need native zstd/crypto; 15 loader-fallback/name/error contracts run separately. [#8](https://github.com/bayramog/ludo/issues/8). |
| `test_title_ids_sigil.py` | Real disc/zipped-disc extraction needs native Sigil; 33 portable save/header/name/ranking checks run separately. [#8](https://github.com/bayramog/ludo/issues/8). |
| Backend `test_mod_packages_transactions.py` | One genuine download/install/remove case enters the same unavailable fcntl transaction; all other 213 backend cases selected. [#7](https://github.com/bayramog/ludo/issues/7). |

The manifest is the executable source of exclusion reasons and links. New or
unclassified test files fail selection rather than disappearing. Native failure
artifacts from the full probe were downloaded and inspected: only bounded JSON
summaries, no raw logs, JUnit, profiles or synthetic credential values.

Regression evidence first reproduced Windows root leakage and forbidden reads
while the auto-sync owner held the real lock, then passed after the fixture
repairs. The Linux/Python 3.13 run at `5ea3d25` also exposed a PCEE2 fixture
race: two real `format_card()` calls across a clock tick produced different
embedded timestamps. A forced-clock-tick regression first failed, then passed
after fixing only the fixture clock; full byte equality and real formatting are
still asserted. The 34 runner/fixture contracts also retain the #249 review regressions:
mixed empty/passing backend selection, parameter/class/unittest file attribution,
setup-error/skip precedence, CRLF completion markers, synthetic boot identity,
subprocess/timeout failures and bounded secret-free evidence.

Inside `test_batch_regressions.py`, the two POSIX owner-mode assertions only
execute on POSIX. Windows still executes credential migration/encryption/readback,
prints the limitation, and retains [F1-01 #6](https://github.com/bayramog/ludo/issues/6)
for Windows ACL/device acceptance. This is not an ACL verification claim.
