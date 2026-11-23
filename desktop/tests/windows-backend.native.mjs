// Native CI only: real Windows interpreters, backend, pipes, bind and RPC.
// Use a junction to the CI interpreter for the packaged layout. This is not a release ZIP.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { once } from "node:events";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { bootShell } from "./support/backend-shell.mjs";

const repo = fileURLToPath(new URL("../../", import.meta.url));
const next = (events, name) => once(events, name, { signal: AbortSignal.timeout(75000) });
for (const mode of ["development", "packaged layout", "occupied port"]) {
  test(mode + " with the real Windows backend", async t => {
    assert.equal(process.platform, "win32");
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "Ludo İzmir 東京 "));
    t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5 }));
    const packaged = mode !== "development";
    const resources = path.join(root, "resources");
    const desktop = packaged ? path.join(resources, "app-src", "desktop") : path.join(root, "desktop");
    fs.mkdirSync(path.join(desktop, "backend"), { recursive: true });
    for (const file of ["server.py", "windows_lifetime.py"]) {
      const source = path.join(repo, "desktop", "backend", file);
      const target = path.join(desktop, "backend", file);
      fs.copyFileSync(source, target);
      assert.deepEqual(fs.readFileSync(target), fs.readFileSync(source));
    }
    fs.copyFileSync(path.join(repo, "desktop", "package.json"), path.join(desktop, "package.json"));
    const py = (...args) => execFileSync("python", args, { cwd: repo, encoding: "utf8" }).trim();
    if (packaged) {
      fs.symlinkSync(py("-c", "import sys; print(sys.base_prefix)"), path.join(resources, "python"), "junction");
    } else {
      py("-m", "venv", "--system-site-packages", "--without-pip", path.join(desktop, ".venv"));
    }
    const reserve = net.createServer().listen(0, "127.0.0.1");
    await once(reserve, "listening");
    const port = reserve.address().port;
    const closeListener = () => new Promise(resolve => reserve.close(resolve));
    if (mode === "occupied port") t.after(closeListener);
    else await closeListener();

    const env = JSON.parse(py("-c", [
      "import json, sys", "from pathlib import Path", "sys.path.insert(0, 'scripts')",
      "from test_support import fixture_environment", "print(json.dumps(fixture_environment(Path(sys.argv[1]))))",
    ].join("; "), root));
    env.ROMM_PORT = String(port);
    env.PYTHONHOME = "poisoned parent Python home";
    const children = [];
    const { events, ipc, app } = bootShell({
      packaged, desktop, resources, paths: path, env,
      spawn(exe, args, opts) {
        assert.equal(opts.windowsHide, true);
        const child = spawn(exe, args, opts);
        children.push(child);
        return child;
      },
    });
    t.after(() => {
      for (const child of children) if (child.exitCode === null && child.signalCode === null) child.kill();
    });
    // A real startup error should fail immediately and include Python's diagnostic.
    const startup = Promise.race([
      next(events, "load").then(() => "loaded"), next(events, "dialog").then(([msg]) => msg),
    ]);
    if (mode === "occupied port") {
      assert.match(await startup, /10048|10013|address already in use/i);
      assert.ok(children[0].exitCode);
      return;
    }
    assert.equal(await startup, "loaded");
    const rpc = async (method, ...args) => {
      const res = await fetch(`http://127.0.0.1:${port}/api/${method}`, {
        method: "POST", body: JSON.stringify({ args }), signal: AbortSignal.timeout(5000),
      });
      const reply = await res.json();
      assert.ok(!reply.error, reply.error);
      return reply.result;
    };
    assert.equal((await rpc("get_profiles")).current, "default");
    const created = await rpc("create_profile", "İzmir 東京");
    assert.equal(created.status, "reload");
    const reloaded = next(events, "load");
    ipc.emit("romm:reload-backend");
    await reloaded;
    assert.equal(children.length, 2);
    assert.equal(children[0].exitCode, 0, "old backend exited gracefully before rebinding");
    assert.equal((await rpc("get_profiles")).current, created.id);
    const quit = next(events, "quit");
    app.emit("window-all-closed");
    await quit;
    assert.equal(children[1].exitCode, 0);
  });
}
