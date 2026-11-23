import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { test } from "node:test";
import vm from "node:vm";

const main = new URL("../electron/main.cjs", import.meta.url);
const requireMain = createRequire(main);
const resources = String.raw`C:\Oyun Alanı\東京\resources`;
const desktop = String.raw`C:\Kaynak Kod\İzmir\desktop`;

// Exercise the shell's real boot callback without opening a GUI.
async function launch(packaged, expected) {
  const proc = Object.assign(new EventEmitter(), {
    argv: [], env: { ROMM_PORT: "8723" }, platform: "win32",
    resourcesPath: resources, stdout: new EventEmitter(), stderr: new EventEmitter(),
  });
  const app = Object.assign(new EventEmitter(), {
    isPackaged: packaged, getPath() { return desktop; }, setName() {}, setPath() {},
    commandLine: { appendSwitch() {} }, requestSingleInstanceLock: () => true,
    whenReady: () => Promise.resolve(), quit() {},
  });
  let spawnArgs, message;
  const electron = {
    app, protocol: { registerSchemesAsPrivileged() {} }, ipcMain: { on() {}, handle() {} },
    dialog: { showErrorBox(_title, detail) { message = detail; } },
  };
  const modules = {
    electron, path: path.win32, fs: { existsSync: p => p === expected },
    child_process: { spawn(...args) { spawnArgs = args; throw new Error("fixture launch failed"); } },
  };
  vm.runInNewContext(fs.readFileSync(main, "utf8"), {
    require: name => modules[name] ?? requireMain(name),
    process: proc, __dirname: path.win32.join(desktop, "electron"),
    console: { error() {}, log() {} }, setTimeout, clearTimeout,
  });
  await new Promise(resolve => setImmediate(resolve));
  return { spawnArgs, message };
}

for (const [mode, packaged, expected] of [
  ["packaged", true, path.win32.join(resources, "python", "python.exe")],
  ["development", false, path.win32.join(desktop, ".venv", "Scripts", "python.exe")],
]) {
  test(mode + " Windows shell launches Python from a spaced Unicode path", async () => {
    const { spawnArgs, message } = await launch(packaged, expected);
    assert.equal(spawnArgs?.[0], expected);
    assert.equal(spawnArgs[1].length, 1);
    assert.equal(spawnArgs[1][0], path.win32.join(packaged ? path.win32.join(resources, "app-src", "desktop") : desktop, "backend", "server.py"));
    assert.equal(spawnArgs[2].windowsHide, true);
    assert.match(message, /fixture launch failed/);
  });
}
