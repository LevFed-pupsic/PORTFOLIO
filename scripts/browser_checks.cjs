/* Optional development check: npm install --no-save playwright @axe-core/playwright.
   Run ONLY against a local preview with an isolated DATABASE_PATH.
   BROWSER_PATH=/usr/bin/chromium node scripts/browser_checks.cjs */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const base = process.env.TEST_URL || "http://127.0.0.1:4173";
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname))
  throw Error("Local test target required");
const out = path.resolve("docs/screenshots");
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.BROWSER_PATH || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  });
  const errors = [],
    failures = [],
    viewports = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("response", (r) => {
    if (r.status() >= 400) failures.push(`${r.status()} ${r.url()}`);
  });
  for (const route of ["/", "/portfolio", "/privacy"]) {
    for (const width of [320, 375, 390, 768, 1024, 1440, 1920]) {
      await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
      await page.goto(base + route);
      await page.waitForTimeout(100);
      const sizes = await page.evaluate(() => ({
        client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      assert.ok(sizes.scroll <= sizes.client, `${route} overflow at ${width}`);
      viewports.push({ route, width, ...sizes, overflow: false });
      if (route === "/") {
        const title = await page.locator("h1").boundingBox(),
          photo = await page.locator(".hero-photo").boundingBox();
        assert.ok(
          title.x + title.width <= photo.x + 1 ||
            title.y + title.height <= photo.y + 1,
          `Portrait overlaps heading at ${width}`,
        );
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base);
  const anchors = await page
    .locator('a[href*="#"]')
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href")));
  for (const href of anchors) {
    const id = href.split("#")[1];
    if (id) assert.equal(await page.locator(`[id="${id}"]`).count(), 1, href);
  }
  for (const [category, count] of [
    ["portrait", 2],
    ["editorial", 1],
    ["travel", 3],
    ["all", 6],
  ]) {
    await page.locator(`[data-filter="${category}"]`).click();
    assert.equal(await page.locator(".work:not([hidden])").count(), count);
  }
  await page.locator(".photo-button").first().click();
  assert.equal(await page.locator("dialog").evaluate((d) => d.open), true);
  const first = await page.locator(".lightbox-image").getAttribute("src");
  await page.keyboard.press("ArrowRight");
  assert.notEqual(
    await page.locator(".lightbox-image").getAttribute("src"),
    first,
  );
  await page.keyboard.press("ArrowLeft");
  assert.equal(
    await page.locator(".lightbox-image").getAttribute("src"),
    first,
  );
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press("Tab");
    assert.ok(
      await page.evaluate(() => !!document.activeElement.closest("dialog")),
    );
  }
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("dialog").evaluate((d) => d.open), false);
  assert.equal(
    await page
      .locator(".photo-button")
      .first()
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page.locator('[data-service="editorial"]').click();
  assert.equal(await page.locator("#service").inputValue(), "editorial");
  await page.locator("#name").fill("Тест браузера");
  await page.locator("#email").fill("browser-v2@example.com");
  await page
    .locator("#message")
    .fill("Проверка формы MOROZOV v2 в изолированной базе.");
  await page.locator('[name="consent"]').check();
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/inquiries") && r.request().method() === "POST",
  );
  await page.locator("button[type=submit]").click();
  const response = await saved;
  assert.ok([200, 201].includes(response.status()), await response.text());
  await page.waitForFunction(() =>
    document.querySelector("#form-status").textContent.includes("сохранена"),
  );
  assert.equal(await page.locator("#name").inputValue(), "");
  // Exercise mobile menu and touch handler in a touch-enabled context.
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  const mp = await mobile.newPage();
  await mp.goto(base);
  await mp.waitForTimeout(1200);
  await mp.locator(".menu-toggle").click();
  assert.equal(
    await mp.locator(".menu-toggle").getAttribute("aria-expanded"),
    "true",
  );
  await mp.waitForTimeout(350);
  await mp.screenshot({ path: path.join(out, "mobile-menu.png") });
  await mp.locator("nav a").first().click();
  assert.equal(
    await mp.locator(".menu-toggle").getAttribute("aria-expanded"),
    "false",
  );
  await mp.locator(".photo-button").first().click();
  const before = await mp.locator(".lightbox-image").getAttribute("src");
  await mp.locator('.lightbox-image').evaluate(img => {
    const start = new Touch({identifier:1,target:img,clientX:250,clientY:200});
    const end = new Touch({identifier:1,target:img,clientX:80,clientY:200});
    img.dispatchEvent(new TouchEvent('touchstart', {changedTouches:[start],bubbles:true}));
    img.dispatchEvent(new TouchEvent('touchend', {changedTouches:[end],bubbles:true}));
  });
  assert.notEqual(
    await mp.locator(".lightbox-image").getAttribute("src"),
    before,
  );
  await mp.locator(".lightbox-close").click();
  await mp.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await mp.waitForTimeout(500);
  await mp.screenshot({ path: path.join(out, "mobile-390.png") });
  // Reduced motion is toggled at runtime; all animation durations must be zero.
  await mp.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await mp
      .locator(".hero-photo")
      .evaluate((e) => getComputedStyle(e).animationName),
    "none",
  );
  await mp.emulateMedia({ reducedMotion: "no-preference" });
  await mobile.close();
  await page.goto(base);
  await page.waitForTimeout(1300);
  await page.screenshot({ path: path.join(out, "desktop.png") });
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('.skip, .scroll-progress')) el.style.visibility = 'hidden';
  });
  for (const selector of [
    "#work",
    ".feature",
    "#about",
    "#services",
    "#contact",
  ]) {
    const el = page.locator(selector);
    const box = await el.boundingBox();
    for (let y = box.y; y < box.y + box.height; y += 600) {
      await page.evaluate(
        (y) => window.scrollTo({ top: y, behavior: "instant" }),
        y,
      );
      await page.waitForTimeout(140);
    }
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(950);
    await el.screenshot({
      path: path.join(out, `${selector.replace(/[.#]/g, "")}.png`),
    });
  }
  await page.goto(base + "/portfolio");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(out, "portfolio.png") });
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(base);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(out, "laptop-1024.png") });
  // No-JS check: all gallery content and mobile navigation stay reachable.
  const plain = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 390, height: 844 },
  });
  const np = await plain.newPage();
  await np.goto(base);
  assert.equal(await np.locator("nav").isVisible(), true);
  assert.equal(await np.locator(".work").count(), 6);
  assert.equal(await np.locator(".work noscript a").count(), 6);
  await plain.close();
  assert.deepEqual(errors, []);
  assert.deepEqual(failures, []);
  fs.writeFileSync(
    "docs/viewport-results.json",
    JSON.stringify(viewports, null, 2) + "\n",
  );
  fs.writeFileSync(
    "docs/browser-results.json",
    JSON.stringify(
      {
        date: new Date().toISOString(),
        browser: await browser.version(),
        viewports: viewports.length,
        consoleErrors: errors,
        failedResponses: failures,
        checks: [
          "anchors",
          "all filters",
          "modal arrows",
          "modal focus trap",
          "Escape and focus return",
          "service preselection",
          "form response and reset",
          "mobile menu",
          "synthetic swipe",
          "runtime reduced motion",
          "no-JS navigation and photos",
        ],
        formStatus: response.status(),
      },
      null,
      2,
    ) + "\n",
  );
  await browser.close();
  console.log(
    "PASS: 21 route/viewport checks; gallery, keyboard, menu, form, motion, no-JS; no browser errors.",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
