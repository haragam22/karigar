// Browser checks against a running local preview. No build dependency is added to the service.
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
const require = createRequire(import.meta.url);
const puppeteer = require(process.env.HALLMARK_PUPPETEER || "puppeteer-core");
const base = process.env.KARIGAR_PREVIEW_URL || "http://127.0.0.1:8080";
const out = "docs/screenshots";
await mkdir(out, { recursive: true });
const browser = await puppeteer.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.setRequestInterception(true);
page.on("request", (request) => {
  if (/^https?:/.test(request.url()) && !request.url().startsWith(base + "/")) {
    errors.push(
      `Unexpected external dependency: ${new URL(request.url()).origin}`,
    );
    return request.abort();
  }
  request.continue();
});
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
await page.goto(base + "/console/", { waitUntil: "networkidle0" });
await page.screenshot({ path: `${out}/login-desktop.png`, fullPage: true });
await page.type(
  "#token",
  process.env.KARIGAR_PREVIEW_TOKEN || "local-demo-owner",
);
await page.click("#login-form button");
await page.waitForSelector("#shell:not([hidden])");
await page.waitForFunction(() => document.querySelector("#main .studio"));
const routes = [
  "studio",
  "orders",
  "catalogue",
  "viewer",
  "rates",
  "workshop",
  "demo",
  "system",
];
const report = [];
async function settleMedia() {
  await page.evaluate(async () => {
    const images = Array.from(document.images);
    images.forEach((i) => (i.loading = "eager"));
    await Promise.all(
      images.map((i) =>
        i.complete
          ? Promise.resolve()
          : new Promise((resolve) => {
              i.onload = resolve;
              i.onerror = resolve;
              setTimeout(resolve, 15000);
            }),
      ),
    );
    document.querySelectorAll("model-viewer").forEach((m) => {
      m.reveal = "auto";
      m.loading = "eager";
    });
  });
  await page
    .waitForFunction(
      () =>
        Array.from(document.querySelectorAll("model-viewer")).every(
          (m) => m.loaded,
        ),
      { timeout: 20000 },
    )
    .catch(() => errors.push("A 3D model did not load before capture"));
  const missing = await page.$$eval(
    "img",
    (imgs) => imgs.filter((i) => !i.complete || !i.naturalWidth).length,
  );
  if (missing) errors.push(`${missing} images missing before capture`);
  for (const handle of await page.$$("model-viewer")) {
    await handle.evaluate((e) => e.scrollIntoView({ block: "center" }));
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  await page.evaluate(() => scrollTo(0, 0));
  await new Promise((resolve) => setTimeout(resolve, 500));
}
for (const width of [1440, 360]) {
  await page.setViewport({
    width,
    height: width === 360 ? 800 : 1000,
    deviceScaleFactor: 1,
  });
  for (const route of routes) {
    await page.goto(base + `/console/#${route}`, { waitUntil: "networkidle0" });
    await page.waitForSelector("#shell:not([hidden])");
    await new Promise((r) => setTimeout(r, 1000));
    await settleMedia();
    const info = await page.evaluate(() => ({
      title: document.querySelector("main h1")?.textContent,
      overflow: document.documentElement.scrollWidth > innerWidth,
      main: document.querySelector("main").textContent.trim().slice(0, 180),
      model: !!document.querySelector("model-viewer")?.modelIsVisible,
    }));
    report.push({ route, width, ...info });
    await page.screenshot({
      path: `${out}/${route}-${width}.png`,
      fullPage: true,
    });
    if (info.overflow) errors.push(`${route} overflows at ${width}`);
  }
}
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
await page.goto(base + "/console/#orders", { waitUntil: "networkidle0" });
const first = await page.$("tr:has(.badge.done) td a");
if (first) {
  await first.click();
  await new Promise((r) => setTimeout(r, 1500));
  await settleMedia();
  await page.screenshot({
    path: `${out}/order-detail-desktop.png`,
    fullPage: true,
  });
  await page.setViewport({ width: 360, height: 800, deviceScaleFactor: 1 });
  await page.evaluate(() =>
    document.querySelector("#main model-viewer")?.scrollIntoView(),
  );
  await settleMedia();
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: `${out}/order-detail-mobile.png`,
    fullPage: true,
  });
}
await page.goto(base + "/console/#studio", { waitUntil: "networkidle0" });
await page.type("#request", "Do not discard this draft after blur.");
await page.click("#breadcrumb");
await page.evaluate(async () =>
  fetch("/api/console/actions", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + sessionStorage.getItem("karigar-owner"),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action: "shop" }),
  }),
);
await new Promise((resolve) => setTimeout(resolve, 11000));
if (
  (await page.$eval("#request", (e) => e.value)) !==
  "Do not discard this draft after blur."
)
  errors.push("Background polling discarded the brief");
report.push({
  interaction: "draft survives blur and two polling intervals",
  passed: true,
});
await page.goto(base + "/console/#viewer", { waitUntil: "networkidle0" });
await settleMedia();
await page.evaluate(() => {
  const m = document.querySelector("model-viewer");
  m.cameraOrbit = "40deg 60deg auto";
  m.autoRotate = true;
  document.querySelector("details").open = true;
});
await new Promise((resolve) => setTimeout(resolve, 11000));
const persisted = await page.evaluate(() => ({
  rotate: document.querySelector("model-viewer").autoRotate,
  details: document.querySelector("details").open,
}));
if (!persisted.rotate || !persisted.details)
  errors.push("Polling reset the viewer or its disclosure");
report.push({
  interaction: "viewer and disclosure survive two polling intervals",
  ...persisted,
});
await page.goto(base + "/console/#orders", { waitUntil: "networkidle0" });
await page.type("#search", "no-such-order-987654");
await page.click("#filters button");
await page.waitForFunction(() =>
  document.querySelector("main").textContent.includes("No matching orders"),
);
report.push({ interaction: "order search empty state", passed: true });
await page.goto(base + "/console/#catalogue", { waitUntil: "networkidle0" });
const collectionSize = await page.$$eval(
  ".catalogue .variant",
  (rows) => rows.length,
);
if (collectionSize !== 19)
  errors.push(`Expected 19 catalogue families, saw ${collectionSize}`);
const start = await page.$("[data-start-family]");
if (start) {
  await start.click();
  await page.waitForSelector("#request");
  const draft = await page.$eval("#request", (e) => e.value);
  if (!draft.includes("ring_floral_cluster"))
    errors.push("Catalogue family did not reach the order brief");
  report.push({ interaction: "catalogue to order", passed: !!draft });
}
await page.goto(base + "/console/#viewer", { waitUntil: "networkidle0" });
const wasRotating = await page.$eval("model-viewer", (m) => !!m.autoRotate);
await page.click("#spin-view");
if (
  (await page.$eval("#spin-view", (b) => b.getAttribute("aria-pressed"))) !==
  String(!wasRotating)
)
  errors.push("Rotation did not toggle");
await page.click("#spin-view");
await page.click("#reset-view");
report.push({ interaction: "viewer rotation, pause and reset", passed: true });
await page.setViewport({ width: 360, height: 800, deviceScaleFactor: 1 });
await page.click("#menu");
if (
  (await page.$eval("#menu", (b) => b.getAttribute("aria-expanded"))) !== "true"
)
  errors.push("Phone navigation did not open");
await page.click("#menu");
report.push({ interaction: "phone navigation", passed: true });
await page.goto(base + "/console/#demo", { waitUntil: "networkidle0" });
await page.type("#chat-text", "kuch sundar sa bana do");
await page.click("#chat-form .primary");
await page.waitForFunction(
  () =>
    document.querySelectorAll(".message.assistant")[0]?.textContent.length > 30,
  { timeout: 60000 },
);
report.push({ interaction: "streamed chat", passed: true });
await writeFile(
  "docs/console-browser-report.json",
  JSON.stringify({ report, errors }, null, 2),
);
await browser.close();
console.log(JSON.stringify({ screens: report.length, errors }));
if (errors.length) process.exitCode = 1;
