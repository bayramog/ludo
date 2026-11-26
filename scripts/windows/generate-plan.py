import argparse
import collections
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description='Generate the versioned Windows issue catalog and support inventory.')
parser.add_argument('--source', type=Path, required=True, help='RetroBat 8.3.1 es_systems.cfg downloaded from the URL below')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/windows'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = args.source
SOURCE_URL = 'https://github.com/RetroBat-Official/retrobat/blob/8.3.1/system/templates/emulationstation/es_systems.cfg'

# id, title, dependencies, scope, acceptance evidence
DEFS = [
('F0-01', 'Prepare fork issue tracking and upstream baseline', [],
 'Enable Issues in bayramog/ludo; create one tracking epic and six milestones. Preserve fork commits while integrating upstream beta.33 on a separate baseline branch. Keep upstream free of planning posts.',
 ['Issue links, milestone assignments and dependency graph are read back from GitHub.', 'Record the exact fork and upstream SHAs, merge ancestry and baseline failures.', 'Publish the support policy and contribution/release requirements; do not mark runtime support complete.']),
('F0-02', 'Establish Windows and Linux compatibility baselines', ['F0-01'],
 'Record Windows 11 x64 desktop, Linux desktop and Decky baselines. Inventory interpreter, Electron, frontend and emulator versions and distinguish unsupported hardware from a failing regression.',
 ['Run real Windows tests and clean-user startup; retain logs, versions and test counts.', 'Record Linux desktop and Decky regression evidence against the same commit.', 'Track pre-existing failures individually; skipped or mocked platform execution is never a Windows pass.']),
('F0-03', 'Decide backend lifetime and external-launch behavior', ['F0-01'],
 'Compare Linux desktop window-close shutdown with Decky plugin lifetime. Present tray/session-process/service choices, startup ownership, frontend game-start synchronization, shutdown and suspend behavior. The user explicitly deferred this decision.',
 ['Document observed Linux and Decky lifecycle, including concurrent shells and lock ownership.', 'Present concrete options and obtain the user decision before changing persistent/background operation.', 'Specify launch barrier, timeout/offline policy, process ownership and bounded shutdown from that decision.']),
('F0-04', 'Freeze the RetroBat emulation support matrix', ['F0-01'],
 'Pin RetroBat 8.3.1 manifest and enumerate every system/emulator/core variant. Classify emulation versus native games, source ports, storefronts and utilities. Keep system aliases and user-selected backend overrides explicit.',
 ['Every included variant links to an EMU or CORE issue; excluded and review-needed rows have reasons.', 'Resolve RomM platform IDs from authoritative server metadata, never assume frontend slugs equal RomM IDs.', 'Record native save/state capability and authoritative versioned sources; unknown stays unknown.', 'Reconcile duplicates, multi-system adapters and newly changed upstream manifests before claiming matrix completion.']),
('F1-01', 'Make application paths and settings Windows-safe', ['F0-01'],
 'Resolve per-user Windows state in LOCALAPPDATA while preserving existing Linux/Decky paths and existing user libraries. Make atomic settings persistence work without Unix-only permission APIs. Handle Unicode, spaces, drive paths and test isolation.',
 ['Windows saves and reloads settings/credentials in a fresh profile without fchmod/pwd failures.', 'Legacy Linux/Decky config and RomMSync libraries remain readable; no silent move or cross-profile fallback.', 'Atomic-write failure preserves the previous file and closes descriptors; UTF-8 round trips.', 'Tests isolate HOME, USERPROFILE and app-data roots and assert actual source import locations.']),
('F1-02', 'Implement cross-platform sync and install locking', ['F1-01'],
 'Share a small process-lock primitive between AutoSyncLock and installation ownership. Use native Windows locking and preserve Linux desktop/Decky contention semantics. Keep stable lock-file identity to avoid unlink/recreate races.',
 ['Separate processes contend for one lock; only one owner can sync or install.', 'Normal release, process crash and repeated acquisition release ownership correctly.', 'Permission and I/O failures are visible and distinguishable from another live owner.', 'Real Windows and Linux multiprocessing tests cover lock file persistence and duplicate acquire/release.']),
('F1-03', 'Implement Windows backend and process lifecycle', ['F1-01','F1-02'],
 'Resolve embedded Windows Python, start a hidden backend with isolated startup environment and shut it down predictably. Replace /proc-only runtime probes where Windows requires them. Preserve upstream bounded RPC drain and Linux semantics; background policy remains F0-03.',
 ['Packaged python/python.exe and dev Scripts/python.exe launch with Unicode/spaced paths.', 'Startup errors and occupied ports surface; owned process trees terminate within a bound.', 'PID reuse, external emulator processes, suspend/resume and child pipe output are tested.', 'Window-close behavior remains explicit and separate from the deferred background policy.']),
('F1-04', 'Bundle Windows native dependencies and archive support', ['F0-02','F1-01'],
 'Build or source Windows x64 Sigil, zstd, crypto and 7-Zip dependencies with pinned provenance, integrity and licenses. Update loaders/package data without relying on globally installed binaries.',
 ['Clean Windows machine imports bundled DLLs and extracts zip/7z/NSZ fixtures.', 'Dependency architecture, transitive DLLs, hashes, source versions and redistribution notices are recorded.', 'Linux bundled .so behavior remains covered; missing optional capability yields actionable diagnostics.', 'Archive traversal, Unicode filenames, cancellation and partial-output cleanup are tested.']),
('F1-05', 'Build Windows installer and portable packages', ['F1-01','F1-02','F1-03','F1-04','F1-06'],
 'Ship a per-user NSIS installer and a portable ZIP with embedded Python and all runtime dependencies. Define executable/data layout and migration explicitly; portable distribution does not imply moving credentials between devices.',
 ['Install and unzip on Windows 11 x64 without Python, Node or Git; pair and perform a smoke sync.', 'Upgrade, uninstall and rollback preserve user-selected ROM/save locations and settings appropriately.', 'Both artifacts carry the same tag/version and include license/provenance files.', 'Fresh-user, read-only install directory, Unicode paths and relocation behavior have recorded evidence.']),
('F1-06', 'Add real Windows CI and portable test runners', ['F1-01','F1-02'],
 'Provide a Python runner for the standalone engine scripts and execute Windows-native CI alongside Linux. Ensure shell commands, symlinks, home isolation and fixture assumptions are portable. Keep actual build/render coverage, not typecheck-only gates.',
 ['Windows and Linux run meaningful engine/backend subsets with explicit counts; no zero-test success.', 'Each platform-specific exclusion has a reason and tracked remediation; failures are not silently skipped.', 'Desktop built-dist rendering and host contract tests execute; Decky typecheck remains required.', 'CI jobs record versions and upload failure evidence without credentials.']),
('F2-01', 'Introduce installation profiles and adapter contracts', ['F1-01','F0-04'],
 'Introduce InstallationProfile and launch/save/metadata adapter contracts around shared UI/backend/engine. Separate frontend identity from emulator runtime and installer ownership. Migrate legacy settings without forcing new setup.',
 ['Two installations with identical ROM filenames cannot leak configuration or save destinations.', 'Legacy settings migrate with rollback and retain effective paths; disconnected profiles fail explicitly.', 'RetroBat, standalone ES-DE and EmuDeck-managed ES-DE can coexist.', 'Contracts expose capability/evidence state without duplicating business logic in shells.']),
('F2-02', 'Discover and resolve RetroBat installations', ['F2-01'],
 'Resolve RetroBat root, effective system/user overrides, emulator folders, ROM/media/save paths and removable drives. Offer explicit installation selection and validate executable ownership before launch.',
 ['Discovery is read-only and handles multiple roots, portable drives and Unicode/spaced paths.', 'Per-game/core overrides win according to RetroBat launcher behavior.', 'Missing/moved drives produce a profile error instead of selecting another installation.', 'Versioned real config fixtures and clean-machine discovery tests are committed.']),
('F2-03', 'Launch games through RetroBat’s emulator launcher', ['F2-02','F1-03'],
 'Launch through RetroBat emulatorLauncher.exe with system/emulator/core/controller/game-info context and correct working directory. Preserve its controller/config generation and per-game overrides.',
 ['Argument arrays handle spaces, Unicode, multi-disc and directory ROMs without shell injection.', 'The selected runtime/core and controller mapping match frontend launch behavior.', 'Exit codes and process ownership are observable; failures are actionable.', 'Representative libretro and standalone launches have real Windows evidence.']),
('F2-04', 'Add installation setup and capability diagnostics', ['F2-01','F2-02'],
 'Expose profile selection, discovered paths, scope and capability diagnostics in shared UI through host contracts. Show preview before any frontend/config mutation.',
 ['Keyboard and gamepad can complete setup with multiple or missing installations.', 'Read-only discovery never rewrites frontend files.', 'Unknown save/state capability is visibly unverified rather than advertised as supported.', 'Built UI render tests cover success, partial availability and recovery.']),
('F3-01', 'Generalize save and savestate discovery and restore', ['F2-01','F0-04'],
 'Keep existing RomM sync, conflict and snapshot behavior while adding adapter-based discover/pack/restore/compatibility. Associate files with exact ROM member, installation, runtime, core and version.',
 ['Save and state identity survive multi-disc/region/slot variants and two installations.', 'Restore is atomic, backed up and forbidden while the owning emulator is writing.', 'Shared memory cards, HDD/userdata and container formats do not overwrite unrelated games.', 'Windows/Linux round trips test compatible versions; incompatible states are rejected explicitly.']),
('F3-02', 'Complete RetroArch save and savestate round trips', ['F3-01','F2-03'],
 'Resolve effective RetroArch directories and per-content/core overrides, including slots/auto states and special codec formats. Validate every included libretro core through child issues.',
 ['Battery saves, quick/numbered/auto states and thumbnails retain identity where supported.', 'Shared cards, per-game files and compression formats round trip without unrelated-data loss.', 'Windows/Linux compatibility is evidenced per core and version, not inferred globally.', 'All CORE issues reach evidenced supported or native-not-applicable status.']),
('F3-03', 'Integrate frontend launch and exit synchronization', ['F0-03','F2-03','F3-01'],
 'Implement the approved lifecycle policy at frontend start/end boundaries. Verify actual RetroBat and ES-DE hook timing before relying on a prelaunch synchronization barrier.',
 ['No restore overlaps an active emulator; prelaunch timeout/offline/conflict behavior is explicit.', 'Exit/crash/suspend and frontend-launched games produce bounded, retryable upload behavior.', 'Windows script arguments are handled safely; no credentials in hook arguments/logs.', 'Real external launches and Linux/Decky regression scenarios match F0-03 decision.']),
('F4-01', 'Add managed frontend metadata export', ['F2-01'],
 'Export RomM to frontend with stable RomM identity, a managed-field ledger, preview, backups and incremental writes. Preserve user frontend edits and do not reverse-sync scraped metadata to RomM.',
 ['Repeated export is idempotent; user edits survive update/removal/rename conflicts.', 'Concurrent frontend writes are detected and resolved without losing data.', 'XML/paths/media are escaped and writes are atomic with rollback.', 'Deletion, stale media and partial download behavior are tested.']),
('F4-02', 'Export RomM games and media to RetroBat', ['F4-01','F2-02'],
 'Implement the RetroBat-specific gamelist/media adapter using effective system paths, stable ROM IDs and supported media fields. Preserve favorites, play history and frontend-owned fields.',
 ['Titles, descriptions, covers and supported metadata resolve in real RetroBat.', 'Multi-file ROMs and custom system paths export without duplicate entries.', 'Preview and backups demonstrate preservation of user-modified fields.', 'Frontend open/closed export and recovery have integration evidence.']),
('F4-03', 'Support standalone and portable ES-DE installations', ['F4-01','F2-01'],
 'Resolve ES-DE configuration including portable.txt and custom systems; implement its own documented gamelist schema rather than assuming legacy EmulationStation compatibility.',
 ['Installed and portable ES-DE use correct roots and relative-path rules.', 'User overrides and media paths survive repeated export and relocation.', 'Game launches and save mapping reuse profile adapters with per-profile ownership.', 'Real ES-DE versioned evidence covers launch, metadata and external sync hooks.']),
('F4-04', 'Resolve EmuDeck Windows installations', ['F4-03'],
 'Treat EmuDeck as the installation/configuration manager and reuse the ES-DE adapter when present. Derive actual emulator/config roots from installation state, including custom storage.',
 ['EmuDeck-owned ES-DE is not duplicated as a second unrelated installation.', 'Config reset/update and relocated storage trigger safe re-discovery and preview.', 'Standalone ES-DE and EmuDeck coexist without profile leakage.', 'Windows installation fixtures and real launch/save/metadata scenarios are recorded.']),
('F5-01', 'Validate Windows desktop and handheld interaction', ['F1-05','F2-04'],
 'Verify controller-first use and keyboard/mouse on Windows desktop and handheld. Cover focus, fullscreen, hotplug, scaling, sleep and resume.',
 ['Gamepad hotplug and focus restoration work through setup, launch and errors.', 'Multiple DPI/scaling and handheld layouts remain readable and navigable.', 'Sleep/resume and frontend transitions preserve process and sync ownership.', 'Device/OS/runtime versions and reproducible evidence accompany acceptance.']),
('F5-02', 'Separate fork updates and platform update strategies', ['F1-05'],
 'Add explicit release source and update strategy. Fork builds use bayramog/ludo; installed Windows uses its updater strategy, portable ZIP uses manual replacement, and Linux/Decky behavior remains compatible.',
 ['Fork installs cannot download upstream artifacts or another platform’s binaries.', 'Installer update, portable manual update and rollback preserve data and version identity.', 'UI capabilities dispatch the selected strategy instead of calling AppImage update directly.', 'Offline, failed/invalid artifacts and version transitions have tests and provenance.']),
('F5-03', 'Extend release gates and contribution documentation', ['F1-06','F1-05','F5-02'],
 'Extend the same-tag/version release invariant to Windows installer and ZIP alongside Linux AppImage and Decky ZIP. Make required tests publication gates and correct stale contribution/release instructions.',
 ['Release requires successful platform tests/builds and explicit artifact/version verification.', 'No published tag is rewritten and no partial platform release is silently accepted.', 'Windows prerequisites, local tests, generated artifacts and contribution scopes are documented.', 'Release rehearsal validates assets and rollback without publishing a production release.']),
('F5-04', 'Complete the integration acceptance matrix', ['F0-02','F0-04','F3-02','F3-03','F4-02','F4-03','F4-04','F5-01','F5-03'],
 'Close the program only after every included EMU/CORE variant has evidence and full installation/launch/sync/export/upgrade flows pass. Keep outstanding cases visible instead of declaring partial coverage complete.',
 ['Every included matrix row has a resolved RomM mapping and linked acceptance evidence.', 'All EMU/CORE issues are evidenced supported or native-not-applicable; no unknown silently passes.', 'Clean install, upgrade/rollback, two-device round trip, external launch and offline recovery pass.', 'Linux desktop and Decky regressions pass against the final Windows integration commit.']),
]

def issue(id, title, deps, scope, acceptance, kind='foundation', systems=None):
    milestone = 'F3' if id.startswith(('EMU-', 'CORE-')) else id.split('-')[0]
    body = f'<!-- ludo-windows:{id} -->\n## Outcome\n\n{scope}\n\n'
    body += '## Scope and architecture\n\nWindows 11 x64; shared UI/backend/engine and shell adapters. '
    body += 'Preserve Linux desktop and Decky. No native Windows game/storefront integration. '
    body += 'No new background lifetime policy before F0-03.\n\n'
    body += '## Dependencies\n\n' + (', '.join(deps) if deps else 'None; program entry point.') + '\n\n'
    if systems:
        body += '## Manifest variants\n\n' + '\n'.join('- ' + v for v in systems) + '\n\n'
    body += '## Acceptance evidence\n\n' + '\n'.join('- [ ] ' + s for s in acceptance) + '\n\n'
    body += ('## Implementation and verification\n\nOne scoped branch and fork PR. Follow upstream CONTRIBUTING.md: Conventional Commits, '
             'shared shell contracts, documented artifact generation and real built-UI tests when UI changes. '
             'Attach exact commit, OS/runtime/emulator versions, automated results and live evidence. '
             'Record known failures and unsupported native features explicitly. Code merged alone is not completion. '
             'For data writes, demonstrate backup, failed-write recovery and migration/rollback.\n\n'
             '## Sources\n\n- [Upstream contribution guide](https://github.com/rommapp/ludo/blob/0172458/CONTRIBUTING.md)\n'
             '- [Upstream release contract](https://github.com/rommapp/ludo/blob/0172458/RELEASING.md)\n'
             f'- [Pinned RetroBat 8.3.1 manifest]({SOURCE_URL})\n\n'
             'Research snapshot: 2026-11-15. Native capabilities and RomM mappings remain unverified until evidenced.\n')
    return dict(id=id, title=f'[{id}] {title}', milestone=milestone, labels=['windows', kind], dependencies=deps, body=body)

issues = [issue(*d, kind='decision' if d[0]=='F0-03' else 'foundation') for d in DEFS]
raw = SOURCE.read_bytes()
if hashlib.sha256(raw).hexdigest() != 'ab9ddf3a05cc93d3d1b54f0d47e4e9796c0e3bb226857c45501f0422e5bc476a':
    raise SystemExit('Source differs from the reviewed RetroBat 8.3.1 manifest; review scope before regenerating.')
systems = []
runtimes = collections.defaultdict(set)
cores = collections.defaultdict(set)
seen = collections.Counter()
excluded_names = {'amazon','steam','gog','epic','eagames','Windows','recomp','flash'}
review_names = {'pico8','tic80','wasm4','lowresnx','vircon32'}
for s in ET.fromstring(raw):
    name = s.findtext('name')
    seen[name] += 1
    key = name if seen[name] == 1 else f'{name}#{seen[name]}'
    hardware = s.findtext('hardware')
    backends = []
    if name in review_names:
        status, reason = 'excluded', 'Fantasy-console runtime: user excluded these on 2026-11-15 to focus on existing hardware emulation.'
    elif name in excluded_names or hardware in ('port','pinball','system',None,'MESS'):
        status = 'excluded'
        reason = ('Storefront/native Windows games, recompilation or web runtime.' if name in excluded_names else
                  'Source port/native game or engine.' if hardware=='port' else
                  'Pinball simulator/native game; outside console/handheld/arcade/computer emulation scope.' if hardware=='pinball' else
                  'Utility or placeholder, not a launchable emulated system.')
    else:
        status, reason = 'included', 'Console, handheld, arcade, computer or hardware expansion emulation.'
    for e in s.findall('./emulators/emulator'):
        emulator = e.get('name')
        variants = [c.text.strip() for c in e.findall('.//core') if c.text and c.text.strip()]
        ids = [f'CORE-{c}' for c in variants] if emulator=='libretro' else [f'EMU-{emulator}']
        backends.append(dict(emulator=emulator, cores=variants, tracking_ids=ids if status=='included' else [], save='unknown', savestate='unknown', evidence=[]))
        if status == 'included':
            if emulator == 'libretro':
                for c in variants:
                    cores[c].add(key)
            else:
                runtimes[emulator].add(key + (': ' + ', '.join(variants) if variants else ''))
    systems.append(dict(id=key, system=name, name=s.findtext('fullname'), hardware=hardware,
                        scope=status, scope_reason=reason, frontend_platform=s.findtext('platform'),
                        romm_platform=None, romm_mapping_status='unverified', path=s.findtext('path'),
                        extensions=(s.findtext('extension') or '').split(), command=s.findtext('command'), backends=backends))

for name, variants in sorted(runtimes.items()):
    issues.append(issue(f'EMU-{name}', f'Support {name} saves and savestates on Windows', ['F0-04','F2-03','F3-01'],
        f'Implement and validate the {name} runtime adapter for every listed RetroBat 8.3.1 system/core variant. Reuse shared adapters where appropriate but retain variant-specific evidence. Launch through the selected RetroBat installation and resolve its effective configuration.',
        ['Record executable/version, effective configuration, game identity and RomM platform mapping for every listed variant.',
         'Discover, upload and restore per-game saves without copying unrelated shared cards/HDD/userdata.',
         'Validate savestate slots, compression and version compatibility; if native states are absent, link authoritative versioned proof and mark N/A.',
         'Record real Windows round trips, process-active rejection, offline recovery and compatible Linux transfer where available.',
         'Retain fixture tests and live evidence per variant; unknown/unsupported Ludo behavior remains open.'], 'emulator', sorted(variants)))
for name, variants in sorted(cores.items()):
    issues.append(issue(f'CORE-{name}', f'Validate {name} Windows synchronization', ['F0-04','F3-01'],
        f'Validate the {name} libretro core for every listed RetroBat 8.3.1 system. Reuse the RetroArch adapter and extend codecs only where the actual format requires it.',
        ['Pin Windows core/RetroArch versions and resolve each system to authoritative RomM metadata.',
         'Round trip battery save, numbered/auto/quick states and associated thumbnails where natively supported.',
         'Verify effective save/state directories, core/content overrides, region/member identity and special containers.',
         'Record real Windows and compatible Linux transfer evidence, or explicit version/format incompatibility.',
         'A native missing feature requires authoritative proof; unimplemented/unverified support cannot be closed as N/A.'], 'libretro', sorted(variants)))

matrix = dict(schema_version=1, generated_on='2026-11-15', source=dict(url=SOURCE_URL, tag='8.3.1', sha256=hashlib.sha256(raw).hexdigest()),
              policy=dict(target='Windows 11 x64', artifacts=['per-user NSIS installer','portable ZIP'],
                          direction='RomM to frontend; preserve user edits', lifetime='decision pending F0-03',
                          status='inventory only; no Windows runtime support claimed'), systems=systems)
(OUT/'support-matrix.json').write_text(json.dumps(matrix,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
(OUT/'issue-catalog.json').write_text(json.dumps(dict(schema_version=1,issues=issues),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
counts=collections.Counter(s['scope'] for s in systems)
print(json.dumps(dict(main=len(DEFS),emulators=len(runtimes),cores=len(cores),issues=len(issues),scope=dict(counts))))
