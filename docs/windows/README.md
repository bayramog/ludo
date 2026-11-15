# Windows integration program

Approved scope, 2026-11-15: Windows 11 x64, a per-user installer and a portable
ZIP, RetroBat hardware emulation, ROM/save/savestate synchronization, and
RomM-to-frontend metadata/media export that preserves frontend user edits.
Standalone/portable ES-DE and EmuDeck-managed installations follow the RetroBat
foundation. Linux desktop and Decky remain supported throughout.

Native Windows games, storefront/account integration, source ports, pinball
simulators and fantasy consoles are outside this program. The user explicitly
excluded PICO-8, TIC-80, WASM-4, LowRes NX and Vircon32 on 2026-11-15.

This is an implementation inventory, **not a Windows support announcement**.
An included row with unknown capability or no live evidence remains unfinished.

## Tracking and order

[Windows integration epic #244](https://github.com/bayramog/ludo/issues/244)
links all 25 main issues and 217 emulator/core issues across six milestones.

[tracking.json](tracking.json) maps stable plan IDs to the actual fork issue URLs
and milestones. [issue-catalog.json](issue-catalog.json) contains the complete
reviewable issue specifications. The GitHub epic is the operational checklist;
issue closure requires evidence, not merely a merged implementation.

| Phase | Outcome | Main issues |
| --- | --- | --- |
| F0 | Fork baseline, compatibility matrix, lifecycle decision, support inventory | 4 |
| F1 | Windows paths, locks, process lifetime, native dependencies, packaging, CI | 6 |
| F2 | Installation profiles, RetroBat discovery/launch and setup diagnostics | 4 |
| F3 | Save/state adapters, RetroArch variants and external launch synchronization | 3 + 217 variant issues |
| F4 | Managed metadata, RetroBat, ES-DE and EmuDeck integration | 4 |
| F5 | Desktop/handheld acceptance, updater separation and release gates | 4 |

Start with F0-01 and F1-01. F1-02 and Windows test infrastructure follow before
packaging. F2 profile contracts precede runtime-specific work. F3-02 owns core
integration; its child validation issues depend on the shared save contract,
not on closing the parent, so there is no parent/child dependency cycle.
Standalone work should start with existing Eden/Cemu behavior, then common
DuckStation/PCSX2/Dolphin/PPSSPP/handhelds, newer consoles and remaining arcade/
computer variants. Sharing an adapter never substitutes for variant evidence.

## Deferred lifecycle decision

F0-03 is an explicit decision gate. Linux desktop currently owns the backend
under Electron and stops it when the app closes. Decky's backend lives with the
plugin host, independently of whether the plugin UI is visible. These are
different lifetimes, despite sharing sync logic and user state.

Compare tray/session process/service and external-launch ownership using actual
Linux/Decky observations, then obtain the user's choice. Do not install a
service, enable startup, or change persistent background behavior in advance.
F3-03 depends on that choice. Path, lock, profile and packaging preparation do
not require deciding it.

## Codebase findings and implementation boundaries

Baseline: fork `dev` at `2388ed4d56d8d8ff04c6252c7c3d87174a3b8d55`, merged
with upstream `dev` beta.33 (`0172458`). The original
`feat/windows-integrations` worktree at `2ce8d178956f77223e88da54f1600768e1bfb621`
is preserved. The full source SHAs and local test evidence belong in
[BASELINE.md](BASELINE.md).

| Area | Observed constraint | Work item |
| --- | --- | --- |
| `ui/app`, `ui/host/contract.ts` | Shared UI uses host capabilities; do not fork the app per OS | F2-01, F2-04 |
| `app/ludo_app/backend.py` | Shared RPC/backend; install lock uses `fcntl`; upstream now bounds shutdown and moves IO off the RPC loop | F1-02, F1-03 |
| `engine/romm_sync_engine/paths.py` | All OSes use `~/.config`; legacy `~/RomMSync` deliberately wins | F1-01 |
| `sync_core.py` settings | Atomic replace uses Unix-only `fchmod`; encrypted state and account fallback require Windows handling | F1-01 |
| `sync_core.py` autosync | `fcntl` plus unlink-on-release can split lock identity; installers use a separate lock | F1-02 |
| `desktop/electron/main.cjs` | Dev knows `Scripts/python.exe`; packaged runtime expects `python/bin/python3` and Windows shutdown kills directly | F1-03 |
| `emulator_saves.py`, `play_sessions.py` | `/proc`, Linux boot identity and signal semantics are not Windows process ownership | F1-03, F3-03 |
| `sync_core.py` launcher | Standalone entries are Eden/Cemu; a save codec does not imply a launch integration | F2-03, EMU issues |
| Existing RetroDeck resolver | Linux flatpak paths and `.so` core parsing do not resolve arbitrary Windows installations | F2-01, F2-02, F4-03 |
| Native loaders/package data | Sigil `.so`, zstd/crypto loading and 7-Zip discovery need bundled Windows equivalents | F1-04 |
| Desktop packaging | Linux AppImage/Python runtime only; no Windows installer or portable ZIP | F1-05 |
| CI/test runners | Ubuntu-only CI and shell engine runner; engine scripts are not pytest | F1-06 |
| Update UI/host profile | AppImage-specific update call and hardcoded upstream release source | F5-02 |
| Metadata | No general managed export adapter; ES-DE's format differs from older EmulationStation | F4-01..04 |

Keep one UI, `LudoBackend` and sync engine. Introduce focused
`InstallationProfile`, launch, save (discover/pack/restore/compatibility) and
metadata contracts. EmuDeck is an installation manager and ES-DE a frontend;
they may describe the same installation, not mutually exclusive profile types.

The existing RomM sync/conflict/snapshot protocol remains the transport.
Identify the ROM member, installation, runtime/core and version before restore.
Do not treat a shared disk/userdata directory as an isolated game's save, or
promise cross-version savestate conversion. A natively absent feature needs an
authoritative versioned reference before it can be marked not applicable.

RetroBat launch must preserve `emulatorLauncher.exe` configuration/controller
generation and effective overrides. Hook timing must be measured before using
frontend scripts as a prelaunch synchronization barrier. Read-only discovery
must not rewrite frontend configuration.

## Pinned coverage inventory

[support-matrix.json](support-matrix.json) records all 244 manifest rows,
including duplicate names, launch templates, extensions, backends and backend
core variants. There are **173 included systems, 71 excluded rows, 92 standalone
runtime IDs and 125 included libretro core IDs**. Each included backend points
to a stable EMU/CORE tracking ID. All save/state capabilities and RomM platform
mappings start unverified; frontend platform strings are not RomM IDs.

Source: [RetroBat 8.3.1 es_systems.cfg](https://github.com/RetroBat-Official/retrobat/blob/8.3.1/system/templates/emulationstation/es_systems.cfg).
SHA-256: `ab9ddf3a05cc93d3d1b54f0d47e4e9796c0e3bb226857c45501f0422e5bc476a`.
The manifest's two `starship` rows have distinct inventory IDs; both are source
ports and excluded. Arcade loaders remain explicitly inventoried under the
agreed arcade scope, without implying all games or saves work.

Regenerate the catalog and matrix from the exact reviewed source:

```sh
python scripts/windows/generate-plan.py --source /path/to/retrobat-8.3.1-es_systems.cfg
```

The generator rejects a different hash. Review a new source/version and its
scope differences before updating the hash or regenerating. Generation does
not publish to GitHub. `tracking.json` records verified publication receipts;
rerunning the generator leaves those receipts alone.

## Contribution and release requirements

Follow upstream [CONTRIBUTING.md](../../CONTRIBUTING.md): Conventional Commits
with area scopes, shared changes tested in both shells, generated artifacts
updated by documented tools, and tests over the real built UI. Use one scoped
branch/worktree and fork PR per implementation issue. The baseline merge is
separate from portability code and retains fork ancestry.

Engine tests are standalone scripts; a green `pytest engine/tests` is not
coverage. Desktop route rendering requires a build and Playwright. Report
skips and known failures rather than counting them as passing tests. Host
simulation on macOS is useful unit coverage but is not a Windows/Linux/Decky
runtime acceptance result.

[RELEASING.md](../../RELEASING.md) requires the existing artifacts to come from
one immutable tag at one version. F5-03 extends that invariant to Windows and
adds publication test gates. Its stale no-tests language must be reconciled
with current CI. Do not publish partial Windows support or rewrite a released
tag. Fork updates must use the fork's release source; portable ZIP updates are
an explicit manual strategy.

## Completion evidence

Each issue records exact commit and OS/runtime/emulator versions, automated
test results, actual platform observations and migration/rollback evidence.
Final acceptance includes clean install, upgrade, offline recovery, two-device
save/state round trips, external frontend launches, metadata preservation,
desktop/handheld interaction and Linux desktop/Decky regression. Any remaining
unknown or unimplemented included variant keeps the final gate open.
