// The profile picker, opened from the account menu, with the pad.
//
// Two regressions, both invisible to a click-only check:
//  - the account menu's faded panel stays mounted (inert) under the picker, and
//    spatial nav picked its rows as targets, so Left/Right dead-ended on a card;
//  - picking the profile already in use ('ok', no restart) left the picker's
//    faded scrim over the app, swallowing every click after it.
//
// Needs `npm run build` first, like the other render tests.
import test, { before, after, describe } from "node:test";
import assert from "node:assert/strict";

import { PAD, distIsBuilt, launchBrowser, openRoute, startServer } from "./support/render-harness.mjs";
import { POPULATED_FIXTURES } from "./support/fixtures.mjs";

let playwright = null;
try { playwright = await import("playwright"); } catch {
  console.warn("[profile-picker.render] playwright not installed — skipping");
}
const SKIP = !playwright ? "playwright is not installed" : !distIsBuilt() ? "no build — run `npm run build`" : false;

const FIXTURES = {
  ...POPULATED_FIXTURES,
  get_profiles: {
    supported: true, current: "default", ask: false, steam: null, steam_accounts: [],
    profiles: [{
      id: "default", name: "tester", custom_name: false, username: "tester", role: "admin",
      avatar: null, steam: [], signed_in: true, current: true, removable: false,
    }],
  },
  switch_profile: { status: "ok" },
};

async function padDirection(page, dir) {
  await page.evaluate((d) => { window.__rommGamepad.direction(d); window.__rommGamepad.direction(null); }, dir);
  await page.waitForTimeout(350);
}
// The focused card's label: its name line (an avatar without a picture shows
// an initial above it).
const focused = (page) => page.evaluate(() => {
  const lines = (document.activeElement?.innerText ?? "").split("\n");
  return lines.find((l) => l === "tester" || l === "Add profile") ?? lines.join("|");
});
const cards = (page) => page.evaluate(() => document.querySelectorAll(".pf-card").length);

async function openPicker(r) {
  // The account pill: the top bar's right-most control (avatar only at this width).
  await r.page.evaluate(() => {
    const pill = [...document.querySelectorAll(".desk-focusable")]
      .filter((e) => { const b = e.getBoundingClientRect(); return b.top < 60 && b.width > 0; })
      .sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left)[0];
    pill.focus();
  });
  await r.page.keyboard.press("Enter");
  await r.page.waitForTimeout(600);
  await r.activateText("Switch profile", { settleMs: 1000 });
  assert.equal(await cards(r.page), 2, "the picker shows the profile and Add profile");
}

describe("profile picker", { skip: SKIP }, () => {
  let srv, browser;
  before(async () => {
    srv = await startServer({ fixtures: FIXTURES });
    browser = await launchBrowser(playwright);
  });
  after(async () => {
    await browser?.close();
    await srv?.close();
  });

  test("Left/Right move between the cards", async () => {
    const r = await openRoute(browser, srv.origin, "/romm-sync-library");
    try {
      await openPicker(r);
      assert.equal(await focused(r.page), "tester");
      await padDirection(r.page, "right");
      assert.equal(await focused(r.page), "Add profile");
      await padDirection(r.page, "left");
      assert.equal(await focused(r.page), "tester");
    } finally { await r.close(); }
  });

  test("picking the profile in use closes the picker", async () => {
    const r = await openRoute(browser, srv.origin, "/romm-sync-library");
    try {
      await openPicker(r);
      assert.equal(await focused(r.page), "tester");
      await r.pressPad(PAD.OK, { settleMs: 1200 });
      assert.equal(await cards(r.page), 0, "the picker is gone");
      const overlays = await r.page.evaluate(() => document.querySelectorAll(".desk-modal").length);
      assert.equal(overlays, 0, "no modal layer is left over the app");
    } finally { await r.close(); }
  });
});

// Two profiles: Manage (Y / right-click / Space) on either card, then back, lands on
// that same card. By itself focus only came back for the pad.
const TWO = {
  ...FIXTURES,
  get_profiles: {
    ...FIXTURES.get_profiles,
    profiles: [
      FIXTURES.get_profiles.profiles[0],
      { id: "p-2", name: "Guest", custom_name: true, username: "", role: "", avatar: null,
        steam: [], signed_in: false, current: false, removable: true },
    ],
  },
};
const focusedPid = (page) => page.evaluate(() => document.activeElement?.closest("[data-pid]")?.dataset.pid ?? null);
const manageOpen = (page) => page.evaluate(() => [...document.querySelectorAll("*")]
  .some((e) => e.childElementCount === 0 && e.textContent === "Rename" && !e.closest("[inert]")));

describe("profile picker, two profiles", { skip: SKIP }, () => {
  let srv, browser;
  before(async () => {
    srv = await startServer({ fixtures: TWO });
    browser = await launchBrowser(playwright);
  });
  after(async () => {
    await browser?.close();
    await srv?.close();
  });

  async function open() {
    const r = await openRoute(browser, srv.origin, "/romm-sync-library");
    await r.page.evaluate(() => {
      const pill = [...document.querySelectorAll(".desk-focusable")]
        .filter((e) => { const b = e.getBoundingClientRect(); return b.top < 60 && b.width > 0; })
        .sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left)[0];
      pill.focus();
    });
    await r.page.keyboard.press("Enter");
    await r.page.waitForTimeout(600);
    await r.activateText("Switch profile", { settleMs: 1000 });
    assert.equal(await cards(r.page), 3);
    return r;
  }

  for (const pid of ["default", "p-2"]) {
    test(`pad: Manage on ${pid} and back lands on ${pid}`, async () => {
      const r = await open();
      try {
        await r.page.focus(`[data-pid="${pid}"]`);
        await r.pressPad(PAD.SECONDARY, { settleMs: 800 });
        assert.ok(await manageOpen(r.page), "Manage opened");
        await r.pressPad(PAD.CANCEL, { settleMs: 800 });
        assert.equal(await manageOpen(r.page), false);
        assert.equal(await focusedPid(r.page), pid);
      } finally { await r.close(); }
    });

    test(`keyboard: Space on ${pid}, Escape, lands on ${pid}`, async () => {
      const r = await open();
      try {
        await r.page.focus(`[data-pid="${pid}"]`);
        await r.page.keyboard.press("Space");
        await r.page.waitForTimeout(800);
        assert.ok(await manageOpen(r.page), "Manage opened");
        await r.page.keyboard.press("Escape");
        await r.page.waitForTimeout(800);
        assert.equal(await focusedPid(r.page), pid);
      } finally { await r.close(); }
    });

    test(`mouse: right-click ${pid}, Escape, lands on ${pid}`, async () => {
      const r = await open();
      try {
        await r.page.evaluate(() => document.activeElement?.blur());
        await r.page.click(`[data-pid="${pid}"]`, { button: "right" });
        await r.page.waitForTimeout(800);
        assert.ok(await manageOpen(r.page), "Manage opened");
        await r.page.keyboard.press("Escape");
        await r.page.waitForTimeout(800);
        assert.equal(await manageOpen(r.page), false);
        assert.equal(await focusedPid(r.page), pid);
      } finally { await r.close(); }
    });
  }
});
