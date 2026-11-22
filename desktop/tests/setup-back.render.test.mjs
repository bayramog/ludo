// Back on a new profile's welcome screen: the button and B both discard the
// unfinished profile and restart into the one it was added from. B pressed
// before the profile list has arrived must still work (it used to do nothing),
// and a lone profile gets no Back at all.
//
// Needs `npm run build` first, like the other render tests.
import test, { before, after, describe } from "node:test";
import assert from "node:assert/strict";

import { PAD, delayRpc, distIsBuilt, launchBrowser, startServer } from "./support/render-harness.mjs";
import { RPC_FIXTURES } from "./support/fixtures.mjs";

let playwright = null;
try { playwright = await import("playwright"); } catch {
  console.warn("[setup-back.render] playwright not installed — skipping");
}
const SKIP = !playwright ? "playwright is not installed" : !distIsBuilt() ? "no build — run `npm run build`" : false;

const profile = (id, extra) => ({
  id, name: id, custom_name: false, username: "", role: "", avatar: null, steam: [],
  signed_in: false, current: false, removable: false, ...extra,
});
const profilesWith = (list) => ({ supported: true, current: "p-new", ask: false, steam: null, steam_accounts: [], profiles: list });
const SIGNED_OUT = { ...RPC_FIXTURES.get_config, configured: false, romm_url: "", username: "" };

const TWO = {
  get_config: SIGNED_OUT,
  get_profiles: profilesWith([profile("default", { signed_in: true }), profile("p-new", { current: true })]),
  discard_profile: { status: "reload", id: "default" },
};
const ONE = {
  get_config: SIGNED_OUT,
  get_profiles: { ...profilesWith([profile("default", { current: true })]), current: "default" },
};

// The wizard, with the shell's reloadBackend counted instead of run.
async function openWizard(browser, origin, { slowProfiles = 0, open = "p-new" } = {}) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.addInitScript((open) => {
    window.__reloads = 0;
    // The window's caches already belong to the open profile, as in the app:
    // otherwise initProfiles swaps them and reloads the page once.
    localStorage.setItem("romm:profile-active", open);
    window.__rommDesktop = { ...(window.__rommDesktop || {}), reloadBackend() { window.__reloads++; } };
  }, open);
  if (slowProfiles) await delayRpc(page, "get_profiles", slowProfiles);
  await page.goto(origin + "/romm-sync-setup", { waitUntil: slowProfiles ? "domcontentloaded" : "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("Welcome to Ludo"));
  return page;
}
const pressB = (page) => page.evaluate((b) => {
  window.__rommGamepad.button(b, true); window.__rommGamepad.button(b, false);
}, PAD.CANCEL);
const reloads = (page) => page.evaluate(() => window.__reloads);
const backButton = (page) => page.evaluate(() =>
  [...document.querySelectorAll(".desk-focusable")].some((e) => e.innerText.trim() === "Back"));

describe("setup wizard Back", { skip: SKIP }, () => {
  let browser;
  before(async () => { browser = await launchBrowser(playwright); });
  after(async () => { await browser?.close(); });

  test("the Back button discards the new profile and restarts", async () => {
    const srv = await startServer({ fixtures: TWO });
    try {
      const page = await openWizard(browser, srv.origin);
      await page.waitForTimeout(500);
      assert.ok(await backButton(page), "Back is offered next to Get started");
      await page.evaluate(() => [...document.querySelectorAll(".desk-focusable")]
        .find((e) => e.innerText.trim() === "Back").click());
      await page.waitForTimeout(400);
      assert.ok(srv.calls.includes("discard_profile"), "discard_profile was called");
      assert.equal(await reloads(page), 1, "the backend restarts once");
      assert.equal(await page.evaluate(() => sessionStorage.getItem("romm:reopen-picker")), "1",
        "the picker opens again after the restart");
      await page.close();
    } finally { await srv.close(); }
  });

  test("B pressed before the profile list arrives still goes back", async () => {
    const srv = await startServer({ fixtures: TWO });
    try {
      const page = await openWizard(browser, srv.origin, { slowProfiles: 1200 });
      await page.waitForTimeout(300);
      assert.ok(!srv.calls.includes("discard_profile"));
      await pressB(page);
      await page.waitForTimeout(1800);
      assert.equal(srv.calls.filter((c) => c === "discard_profile").length, 1, "one discard, once the list came");
      assert.equal(await reloads(page), 1);
      await page.close();
    } finally { await srv.close(); }
  });

  test("a lone profile has no Back, and B does nothing", async () => {
    const srv = await startServer({ fixtures: ONE });
    try {
      const page = await openWizard(browser, srv.origin, { open: "default" });
      await page.waitForTimeout(500);
      assert.ok(!(await backButton(page)), "no Back without another profile");
      await pressB(page);
      await page.waitForTimeout(500);
      assert.ok(!srv.calls.includes("discard_profile"));
      assert.equal(await reloads(page), 0);
      await page.close();
    } finally { await srv.close(); }
  });
});
