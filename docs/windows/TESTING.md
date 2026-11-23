# Portable test execution (F1-06 / #11)

## Current dev adaptation

Base: `f7abe54e8fbe428aab0eaf5b0c0bfd06fff071c8` (#6 paths on upstream
`e3705259`). The first native probe selects all **83 engine files and 23 backend
files** on both OSes. Windows exclusions will be based on this checkout's actual
results. The earlier review below is historical evidence, not this branch's
acceptance result. Upstream `process-locks.yml` is retained unchanged alongside
the portable matrix and complete Linux CI. Cemu's newer AppImage chmod behavior
is retained in the separated Linux integration group.

The native matrix tests fixture data on hosted Windows Server and Ubuntu with
Python 3.11 and 3.13. This is not Windows 11 desktop/handheld, installer/portable
ZIP, emulator, or real RomM-account acceptance.

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
visibly skipped on Windows: Windows invokes Python directly. Its other twenty-six
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

## Measured Windows scope

[The full Windows probe](https://github.com/bayramog/ludo/actions/runs/45068310226)
at `2928fa7` ran all 65 engine files and all 176 backend cases on both Python
versions. All backend cases passed after fixing per-test Windows user roots
and moving play-time fixtures away from pre-epoch local timestamps. The initial
engine probe failed 15 files. Two fixture fixes (native Eden path expectations
and isolated Switch-key profile roots) retain those files in the native gate.
The first selection was 52 engine files plus the complete 176-case backend.
The fork review then audited all thirteen exclusions against their actual
contracts. Whole-file exclusions were too broad for several mixed suites:
portable checks now run separately from their native integration dependencies.
The current inventory is **73 engine files: 62 selected on Windows, 11 explicitly
excluded; all 73 run on Linux**. All 17 backend files / 176 cases remain selected.
No old Linux check label was dropped in the split; real Linux boot identity also
has its own check alongside synthetic session recovery.

| Originally excluded file | Review decision and remaining boundary |
| --- | --- |
| `test_bios_folder.py` | Retained exclusion: these fixtures explicitly select Flatpak config/first-launch trees; the Windows resolver deliberately bypasses that discovery. [#9](https://github.com/bayramog/ludo/issues/9). |
| `test_bios_readiness.py` | Restored 51 portable readiness, download, BIOS option, blank-save and region-fallback checks. Real serial reading moved to `test_bios_readiness_sigil.py` ([#8](https://github.com/bayramog/ludo/issues/8)); POSIX symlink topology moved to `test_bios_readiness_symlinks.py` ([#9](https://github.com/bayramog/ludo/issues/9)). Both integration files remain excluded on Windows. |
| `test_cemu_standalone.py` | Restored resolver, ZIP/7z extraction and argv contracts. Linux executable discovery, chmod and XDG audio repair moved intact to excluded `test_cemu_standalone_linux.py` ([#16](https://github.com/bayramog/ludo/issues/16)). Command construction does not establish native Flatpak/AppImage execution on Windows. |
| `test_decky_stdlib_imports.py` | Restored source-import guards and environment precedence; compare the native Windows fallback with `os.getlogin`, retaining the real Unix `pwd` comparison on Linux. |
| `test_dreamcast_sync.py` | Retained exclusion: disc-derived VMU names feed the real sync/restore path. Replacing Sigil with a stub would remove the end-to-end identity contract. [#8](https://github.com/bayramog/ludo/issues/8). |
| `test_emulator_saves.py` | Restored 12 filesystem/discovery/packing checks; close fixture ZIP handles before cleanup. Live process/zombie/SIGTERM checks moved intact to excluded `test_emulator_saves_process.py` ([#10](https://github.com/bayramog/ludo/issues/10)). |
| `test_flatpak_launcher_path.py` | Restored all nine custom-launcher/config/overlay checks by setting all user-profile roots. This is path resolution, not a native Flatpak launch. |
| `test_flatpak_rom_grant.py` | Restored the argv contract using native fixture path spelling. Checks folder grant, spaces/Unicode and arguments; does not execute Flatpak. |
| `test_launch_core_dir.py` | Retained exclusion: actual product `:/` normalization strips Windows drive prefixes and causes redundant core overrides. Linux lib64 discovery also remains here. This test-infrastructure change does not fix the launcher product issue. [#16](https://github.com/bayramog/ludo/issues/16). |
| `test_play_sessions.py` | Restored queue/upload/heartbeat/stats/recovery coverage. Synthetic clock recovery now uses a synthetic boot identity, plus an unknown-boot case. Excluded `test_play_sessions_linux_boot.py` preserves the real `/proc` boot identity check on Linux; Windows native identity remains [#10](https://github.com/bayramog/ludo/issues/10). |
| `test_switch_content.py` | Restored 88 real synthetic-container/install/ranking checks. Package-presence/load assertions moved intact to excluded `test_switch_content_sigil.py` ([#8](https://github.com/bayramog/ludo/issues/8)). |
| `test_switch_nsz.py` | Real compressed-container round trips remain excluded for missing native zstd/crypto ([#8](https://github.com/bayramog/ludo/issues/8)); 15 loader-fallback/name/error contracts now run separately in `test_switch_nsz_contracts.py`. |
| `test_title_ids.py` | Restored 33 save/header/name/ranking checks. Real disc and zipped-disc identity moved intact to excluded `test_title_ids_sigil.py` ([#8](https://github.com/bayramog/ludo/issues/8)). |

Review regressions first reproduced the false-green mixed empty/passing backend
selection, Windows HOME/USERPROFILE mismatch, and fake-clock recovery's reliance
on host boot identity. Additional CLI tests cover parametrized/class/unittest
file attribution and preserve setup-error/skip precedence. The manifest remains
the executable source of all eleven exclusion reasons and issue links.

Inside `test_batch_regressions.py`, the two POSIX owner-mode assertions only
execute on POSIX. Windows still executes credential migration/encryption/readback,
prints the limitation, and retains [F1-01 #6](https://github.com/bayramog/ludo/issues/6)
for Windows ACL/device acceptance. This is not an ACL verification claim.

Native failure artifacts from the first probes were downloaded and inspected:
only bounded JSON summaries were present; raw logs, JUnit, user profiles and the
synthetic credential fixture values were absent. Backend diagnostics retain
failing test identifiers while stripping parameter values and failure messages.
