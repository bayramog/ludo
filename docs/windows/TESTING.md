# Portable test execution (F1-06 / #11)

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
zero-exit script fails. Backend runs real pytest, parses its private JUnit
counts and rejects zero tests or unexpected skips.

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
visibly skipped on Windows: Windows invokes Python directly. Its other eighteen
negative/execution contracts execute on both OSes. Tracking: [F1-06](https://github.com/bayramog/ludo/issues/11).

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
status/counts, exit codes, timeouts, elapsed time and at most twelve traceback
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
The resulting selection is 52 engine files plus the complete 176-case backend;
Linux continues to run all 65 engine files. No backend file/case is excluded.

The manifest is the executable source of the following exclusions; every
Windows run prints the exact per-file reason and issue URL.

| Files excluded on Windows | Observed dependency / follow-up |
| --- | --- |
| `test_bios_readiness.py`, `test_dreamcast_sync.py`, `test_switch_content.py`, `test_title_ids.py` | Bundled Linux Sigil cannot load; disc/serial/region extraction fails. [F1-04 #8](https://github.com/bayramog/ludo/issues/8). BIOS readiness also contains POSIX relative-path/symlink expectations. |
| `test_switch_nsz.py` | Native zstd/crypto loader cannot supply the libraries for real container round trips. [F1-04 #8](https://github.com/bayramog/ludo/issues/8). |
| `test_emulator_saves.py`, `test_play_sessions.py` | POSIX executable and `/proc`/boot ownership assumptions. [F1-03 #10](https://github.com/bayramog/ludo/issues/10). |
| `test_bios_folder.py`, `test_flatpak_launcher_path.py` | Flatpak/RetroDECK install/config/first-run fixtures do not represent Windows discovery. [F2-01 #9](https://github.com/bayramog/ludo/issues/9). |
| `test_cemu_standalone.py`, `test_flatpak_rom_grant.py` | Linux Flatpak/AppImage command and controller-repair contracts. [F2-03 #16](https://github.com/bayramog/ludo/issues/16). |
| `test_launch_core_dir.py` | Existing `:/` normalization strips Windows drive prefixes; redundant core override observed. Also covers Linux lib64 discovery. [F2-03 #16](https://github.com/bayramog/ludo/issues/16). |
| `test_decky_stdlib_imports.py` | Decky Unix `pwd`/getpass fallback; Windows has no `pwd`. Kept in full Linux, while Windows account and encryption contracts execute separately. [F1-06 #11](https://github.com/bayramog/ludo/issues/11). |

Inside `test_batch_regressions.py`, the two POSIX owner-mode assertions only
execute on POSIX. Windows still executes credential migration/encryption/readback,
prints the limitation, and retains [F1-01 #6](https://github.com/bayramog/ludo/issues/6)
for Windows ACL/device acceptance. This is not an ACL verification claim.

Native failure artifacts from the first probes were downloaded and inspected:
only bounded JSON summaries were present; raw logs, JUnit, user profiles and the
synthetic credential fixture values were absent. Backend diagnostics retain
failing test identifiers while stripping parameter values and failure messages.
