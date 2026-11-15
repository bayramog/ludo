# F0-03: backend lifetime decision brief

Status: **decision deferred by the user**. This brief records source behavior
and alternatives; it does not authorize a tray app, service or startup task.
Tracking: [F0-03 #4](https://github.com/bayramog/ludo/issues/4).

## What the current source does

At upstream beta.33 (`01724585ac8e7ba8c17c8e4f030f60ab573716f6`):

- Electron obtains a single-instance lock and owns its Python backend. Closing
  all windows stops that backend and quits the app. There is no persistent tray
  owner in this path. See `desktop/electron/main.cjs`, `startBackend`,
  `stopBackend`, `window-all-closed` and `before-quit`.
- POSIX shutdown sends SIGINT, with a forced kill after three seconds. The
  current Windows branch terminates directly. `desktop/backend/server.py`
  owns the shared backend loop, prevents new RPC work while stopping and bounds
  draining/cancellation. Its Linux parent-death hook uses `prctl`.
- Decky loads `Plugin(LudoBackend)`. Plugin `_main`/`_unload` start and unload
  backend behavior; visibility of the UI is not its process lifetime.
  See `decky_plugin/main.py`. Closing a Decky panel is therefore not equivalent
  to quitting the desktop application.
- Sync and installation ownership use shared per-user lock paths. Keeping
  another UI/process alive must not introduce a second sync/install owner.

These are code observations. Live Linux/Decky close, crash and suspend tests are
still required by F0-02/F0-03; this brief does not claim those device tests ran.

## Choices to evaluate

| Choice | User-visible behavior | Consequences to validate |
| --- | --- | --- |
| Window-owned backend | Quitting Ludo stops background work, matching current desktop ownership | External frontend games need an explicit launch/start contract or reconciliation next time Ludo opens; UI closure during play must be defined |
| Per-user session/tray owner | Closing the window can leave sync running; Quit must be explicit | Opt-in startup, one backend owner, crash recovery, updater/restart coordination and visible sync/error state need contracts |
| Windows service | Backend lifetime is independent of the UI session | Account/session identity, encrypted credential access, removable drives, launch/interaction ownership and installer privileges require extra design; a system service cannot be assumed equivalent to the user's desktop process |

No option is selected here. A portable ZIP is a distribution choice and does
not by itself decide startup behavior, process lifetime or portable credentials.

## Evidence needed before deciding

1. Observe Linux desktop Quit/window-close and Decky UI-close/plugin-unload
   during idle, download and emulator play. Record process and lock ownership,
   pending work and restart reconciliation on the same code version.
2. Measure RetroBat and ES-DE game-start/game-end hook ordering. Do not assume
   that a hook provides a blocking prelaunch barrier or reliable crash event.
3. For each choice, exercise external launch when Ludo is closed, UI closure
   while playing, offline prelaunch, save conflict, emulator crash, device
   suspend/resume and simultaneous desktop/frontend requests.
4. Define a bounded prelaunch timeout and offline policy, a no-restore-while-
   running invariant, durable pending upload recovery and ownership of child
   processes. Preserve upstream bounded RPC shutdown work.
5. Present the observed tradeoffs to the user and record the selected policy,
   startup preference and explicit Quit behavior before implementing F3-03.

F1 path/lock portability and F2 profile/discovery contracts can proceed without
selecting a background owner. F1-03 should make the existing lifecycle portable;
new persistent behavior belongs behind this decision gate.
