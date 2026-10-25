#!/usr/bin/env node
// Headless-Chromium renders for review (Playwright). Masks in traced SVGs render
// correctly here; cairosvg/librsvg often show them as colour speckle.
//
//   node scripts/render.js svg   in.svg  out.png  --width 494 --height 251 [--scale 2] [--bg "#ffffff"|transparent]
//   node scripts/render.js stack out.png --width 494 --height 251 part1.svg part2.svg ...   (bottom -> top)
//   node scripts/render.js page  in.html out.png [--width 1920 --height 1080] [--scale 1] [--wait 8000]
//
// Install: npm i playwright && npx playwright install chromium
// (or set PLAYWRIGHT_MODULE to an existing playwright install path).
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

function parse(argv) {
  const opts = { width: 1920, height: 1080, scale: 1, wait: 1500, bg: '#ffffff' };
  const pos = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) opts[a.slice(2)] = argv[++i];
    else pos.push(a);
  }
  ['width', 'height', 'scale', 'wait'].forEach((k) => (opts[k] = Number(opts[k])));
  return { opts, pos };
}

async function shoot(html, out, o, waitMs) {
  const tmp = path.resolve(out + '.render.html');
  fs.writeFileSync(tmp, html);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: o.width, height: o.height }, deviceScaleFactor: o.scale });
  await page.goto('file://' + tmp);
  await page.waitForFunction(() => Array.from(document.images).every((i) => i.complete), null, { timeout: 180000 });
  await page.waitForTimeout(waitMs);
  await page.screenshot({ path: out, omitBackground: o.bg === 'transparent' });
  await browser.close();
  fs.unlinkSync(tmp);
  console.log(out);
}

(async () => {
  const [mode, ...rest] = process.argv.slice(2);
  const { opts, pos } = parse(rest);
  const bg = opts.bg === 'transparent' ? 'transparent' : opts.bg;
  if (mode === 'svg') {
    const [src, out] = pos;
    const html = `<html><body style="margin:0;background:${bg}"><img src="file://${path.resolve(src)}" style="display:block;width:${opts.width}px;height:${opts.height}px"></body></html>`;
    await shoot(html, out, opts, opts.wait);
  } else if (mode === 'stack') {
    const [out, ...parts] = pos;
    const layers = parts.slice().reverse().map((p) => `url(file://${path.resolve(p)})`).join(',');
    const html = `<html><body style="margin:0;background:${bg}"><div style="width:${opts.width}px;height:${opts.height}px;background-image:${layers};background-size:100% 100%;background-repeat:no-repeat"></div></body></html>`;
    await shoot(html, out, opts, Math.max(opts.wait, 6000));
  } else if (mode === 'page') {
    const [src, out] = pos;
    await shoot(fs.readFileSync(src, 'utf8'), out, opts, Math.max(opts.wait, 8000));
  } else {
    console.error('usage: render.js svg|stack|page ... (see header)');
    process.exit(1);
  }
})();
