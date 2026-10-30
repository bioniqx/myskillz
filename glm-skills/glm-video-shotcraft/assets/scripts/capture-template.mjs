// capture-template.mjs — Asset capture script template turning real product pages into promo footage.
// General page capture pipeline template: BASE / output directory / routes / selectors exposed as CONFIG.
//
// Outputs the asset trio (source materials for 3D page planes in the promo):
//   1. Full-page 2x screenshots for each route (deviceScaleFactor: 2 for sharp 3D plane textures)
//   2. Per-element cutouts (transparent element-level PNGs with omitBackground for floating UI chips)
//   3. layout.json (bounding boxes for each element in full-page coordinates for layout-accurate positioning)
//
// Usage:
//   node assets/scripts/capture-template.mjs
//
// Prerequisites:
//   1. Target product running locally (CONFIG.BASE accessible)
//   2. npm i puppeteer
//   3. [Critical] Inject realistic fictional demo data before capture.
//
// CONFIG — Customize for target product (the values below are an example "acme-crm" product)
// ======================================================================
const CONFIG = {
  // Target product local address (start app first)
  BASE: 'http://localhost:3000',

  // Output directory for screenshots and layout.json (relative to this script;
  // typically points to Remotion public/textures/live)
  OUT_DIR: '../../public/textures/live',
  LAYOUT_JSON: '../../src/live-layout.json',

  // Viewport: 1920x1080 @2x is standard for 3D page plane textures
  VIEWPORT: { width: 1920, height: 1080, deviceScaleFactor: 2 },

  // Settle time in ms after navigation (waiting for web fonts/async data)
  SETTLE_MS: 600,

  // Route list: each entry = one page to capture
  PAGES: [
    {
      name: 'home',                 // key in layout.json and prefix for screenshot files
      path: '/',                    // Route relative to BASE
      // waitMs: 1500,              // Optional: additional settle wait
      // Elements recorded for bounding box only (saved to layout.<name>.boxes.<key>)
      boxes: [
        // all: true -> record array of all matching bboxes; otherwise first match only
        { key: 'sections', selector: 'main h2', all: true },
      ],
      // Element cutout PNGs + bboxes. omitBackground: true produces transparent background
      // for UI chips floating above page planes
      cutouts: [
        { name: 'nav', selector: 'header, [role="banner"]' },
        { name: 'card', selector: 'article', all: true, max: 12 },       // card1.png, card2.png…
        { name: 'float-search', selector: 'input', parent: true, omitBackground: true },
        { name: 'float-filter', selector: 'main button', omitBackground: true },
      ],
      // Optional: hide elements and take an empty full-page plate
      // for fly-in shots (<name>-empty.png)
      hideForEmptyPlate: 'article',
    },
    {
      name: 'detail',
      // Detail route with mock entity ID
      
      path: '/customers/demo-0001',
      boxes: [
        { key: 'rows', selector: 'table tbody tr, [role="row"]', all: true, max: 8 },
      ],
      cutouts: [],
      // Optional: interactive steps executed before capture
      // Captures supplementary <name>-after.png after interactWaitMs
      interact: () => {
        const tab = [...document.querySelectorAll('button, [role="tab"], a')]
          .find((e) => /Orders/.test(e.textContent ?? ''));
        if (tab) { tab.click(); return true; }
        return false;
      },
      interactWaitMs: 800,
    },
    {
      name: 'reports',
      path: '/reports/weekly',
      waitMs: 1500, // Example: wait for editor / collaborative doc contents to sync
      boxes: [
        { key: 'paras', selector: '.ProseMirror > p', all: true },
      ],
      cutouts: [],
    },
  ],
};
// ======================================================================
// Generic capture logic below, typically does not need modification
// ======================================================================

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, CONFIG.OUT_DIR);
const layoutPath = path.resolve(here, CONFIG.LAYOUT_JSON);
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(path.dirname(layoutPath), { recursive: true });

const browser = await puppeteer.launch();
const page = await browser.newPage();
await page.setViewport(CONFIG.VIEWPORT);

// Wait for fonts to load then settle briefly — avoids capturing FOUT/skeleton screens
const settle = async () => {
  await page.evaluate(() => document.fonts.ready);
  await new Promise((r) => setTimeout(r, CONFIG.SETTLE_MS));
};

// Convert element bbox to whole-page coordinate system (fullPage screenshot coordinate space)
const pageBox = (el) =>
  el.evaluate((e) => {
    const r = e.getBoundingClientRect();
    return { x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height };
  });

const layout = { pageW: CONFIG.VIEWPORT.width };

for (const pg of CONFIG.PAGES) {
  await page.goto(`${CONFIG.BASE}${pg.path}`, { waitUntil: 'networkidle0' });
  await settle();
  if (pg.waitMs) await new Promise((r) => setTimeout(r, pg.waitMs));

  const entry = { pageH: await page.evaluate(() => document.documentElement.scrollHeight) };
  layout[pg.name] = entry;

  // ---- 1. Full-page 2x screenshot ----
  await page.screenshot({ path: `${outDir}/${pg.name}-full.png`, fullPage: true });
  console.log(`captured ${pg.name}-full`, entry.pageH);

  // ---- 2. boxes: bounding box coordinates only ----
  entry.boxes = {};
  for (const b of pg.boxes ?? []) {
    const els = await page.$$(b.selector);
    const picked = b.all ? els.slice(0, b.max ?? els.length) : els.slice(0, 1);
    const boxes = [];
    for (const el of picked) boxes.push(await pageBox(el));
    entry.boxes[b.key] = b.all ? boxes : boxes[0] ?? null;
    console.log(`  boxes.${b.key}:`, boxes.length);
  }

  // ---- 3. cutouts: element PNG + bbox ----
  entry.cutouts = [];
  for (const c of pg.cutouts ?? []) {
    let els = await page.$$(c.selector);
    if (c.parent) {
      // Take parent container of matched element
      const parents = [];
      for (const el of els) {
        const h = await el.evaluateHandle((e) => e.parentElement);
        const p = h.asElement();
        if (p) parents.push(p);
      }
      els = parents;
    }
    const picked = c.all ? els.slice(0, c.max ?? els.length) : els.slice(0, 1);
    for (let i = 0; i < picked.length; i++) {
      const file = c.all ? `${c.name}${i + 1}.png` : `${c.name}.png`;
      const bb = await pageBox(picked[i]);
      try {
        await picked[i].screenshot({
          path: `${outDir}/${file}`,
          omitBackground: !!c.omitBackground,
        });
      } catch (e) {
        console.log(`  cutout miss ${file}:`, e.message);
        continue;
      }
      entry.cutouts.push({ file, ...bb });
      console.log(`  captured ${file}`, bb);
    }
    if (picked.length === 0) console.log(`  cutout miss ${c.name} (no match: ${c.selector})`);
  }

  // ---- 4. Supplementary post-interaction full-page screenshot (optional) ----
  if (pg.interact) {
    const did = await page.evaluate(pg.interact);
    if (did) {
      await new Promise((r) => setTimeout(r, pg.interactWaitMs ?? 800));
      await page.screenshot({ path: `${outDir}/${pg.name}-after.png`, fullPage: true });
      entry.afterPageH = await page.evaluate(() => document.documentElement.scrollHeight);
      console.log(`captured ${pg.name}-after`);
    }
  }

  // ---- 5. Empty plate (optional): hide elements and capture for fly-in shots ----
  if (pg.hideForEmptyPlate) {
    await page.evaluate((sel) => {
      document.querySelectorAll(sel).forEach((el) => { el.style.visibility = 'hidden'; });
    }, pg.hideForEmptyPlate);
    await page.screenshot({ path: `${outDir}/${pg.name}-empty.png`, fullPage: true });
    console.log(`captured ${pg.name}-empty`);
    // Restore visibility
    await page.evaluate((sel) => {
      document.querySelectorAll(sel).forEach((el) => { el.style.visibility = ''; });
    }, pg.hideForEmptyPlate);
  }
}

fs.writeFileSync(layoutPath, JSON.stringify(layout, null, 1));
console.log('wrote', layoutPath);
await browser.close();
