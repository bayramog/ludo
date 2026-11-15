# Baseline evidence — 2026-11-15

This record distinguishes local macOS checks from actual platform acceptance.
The support inventory is not a claim that Windows emulators already work.

## Source identity

| Source | Commit |
| --- | --- |
| Fork `dev` before integration | `2388ed4d56d8d8ff04c6252c7c3d87174a3b8d55` |
| Preserved original `feat/windows-integrations` worktree | `2ce8d178956f77223e88da54f1600768e1bfb621` |
| Upstream `dev`, v1.0.0-beta.33 | `01724585ac8e7ba8c17c8e4f030f60ab573716f6` |
| Conflict-free merge preserving both parents | `3124165` |

Baseline worktree: `feat/windows-baseline`. Implementation begins separately in
`feat/windows-paths`; neither the main clone's `dev` nor the original worktree
was reset or overwritten.

## Local baseline results

Host: macOS arm64; Python 3.12.13; Node 26.13.0. Python dependencies came from
the existing development venv, with `PYTHONPATH` explicitly selecting this
worktree's `engine` and `app` (not its old editable checkout). Desktop dependencies
were installed from beta.33's lockfile using `npm ci` in this worktree.

| Check | Result |
| --- | --- |
| Backend, `python -m pytest -q app/tests` | 173 passed, 130.92 s |
| Engine, `bash engine/tests/run.sh` with isolated user roots | 57 of 63 script files passed; 6 failed below |
| Desktop `npm run typecheck` | Passed |
| Desktop `npm run build` | Passed, Vite 8.3.4; existing chunk/config-loader warnings |
| Desktop built-dist test suite | 100 passed, 0 failed/skipped, 359.61 s |

The six engine failures are baseline platform limitations, not suppressed
checks. They remain tracked by F0-02, F1-03 and F1-04:

| Test file | Observed failure |
| --- | --- |
| `test_bios_readiness.py` | Disc serial/region expectations fail without the bundled Linux Sigil library loading on macOS |
| `test_dreamcast_sync.py` | Product-number-derived save filenames cannot resolve without Sigil |
| `test_emulator_saves.py` | Linux `/proc/<pid>/status` and live-process assumptions |
| `test_play_sessions.py` | Live-session/process detection assumes Linux behavior |
| `test_switch_content.py` | Bundled Linux Sigil cannot load on macOS arm64 |
| `test_title_ids.py` | Bundled Sigil and disc/title-ID extraction unavailable on this host |

Temporary HOME/USERPROFILE/LOCALAPPDATA/APPDATA roots isolate test state. No live
RomM account, emulator installation, user ROM or save library was modified.

## First implementation evidence

F1-01 / [#6](https://github.com/bayramog/ludo/issues/6) implements Windows
LocalAppData resolution, preserves existing legacy state/library directories,
uses UTF-8 atomic settings writes without `fchmod`, resolves the real Windows
account, and treats settings values literally (including percent signs).

The initial path/settings change passed all 173 backend tests again in
130.46 s. Fifteen new path/settings contracts and the existing five credential
key checks passed locally. A regression test first reproduced failure for a
`ROM arşivi %50` directory, then passed after disabling unintended INI template
interpolation. The final commit's Linux CI result must be checked separately;
the earlier full-backend result predates that last small correction.

A native Windows/Linux workflow for Python 3.11 and 3.13 is prepared in
`feat/windows-foundation-ci`. GitHub rejected publishing the workflow because
the current OAuth credential lacks the `workflow` scope. The source changes
were published separately using existing permission. Authorization to extend
the scope is pending; no Windows CI pass is claimed.

Existing Linux/Decky CI was explicitly dispatched on the paths branch. On the
final code commit `7a044ccb45a6fdb85d92251fef5134cf6d22049f`, the
[Linux CI run](https://github.com/bayramog/ludo/actions/runs/43737852064) passed
all 64 engine script files (including `test_windows_paths.py`), 173 backend
tests (37.41 s), Decky typecheck, and desktop typecheck/build/render tests.
The run completed successfully with all three jobs passing. The earlier run on
`e729ca3` was cancelled by workflow
concurrency after the newer commit's run started; it is not an overall pass.

Live Windows 11 desktop/handheld acceptance, Windows packaging, frontend
lifecycle and all emulator round trips remain open program work.

## Reproducibility and limits

The engine's scripts are not pytest tests. Run `engine/tests/run.sh` on Linux
and the explicitly named portability scripts with Python on Windows until
F1-06 supplies a fully portable runner. Do not turn a skipped/unsupported suite
into a passing gate. Keep exact source and runner versions with future results.

The inventory generator verifies the pinned manifest SHA-256, unique issue IDs,
dependency references and included-row coverage. All 242 work issues plus the
epic were created in `bayramog/ludo`, assigned to six milestones, and read back
with matching titles/bodies/milestones. `tracking.json` is the publication
receipt. No upstream issue, PR or production release was published.
