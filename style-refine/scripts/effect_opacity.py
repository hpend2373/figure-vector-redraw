#!/usr/bin/env python3
"""Make opacity variants of ONE effect group inside an SVG asset, plus a side-by-side comparison sheet.

  python3 effect_opacity.py ring.svg --group "color_flow" --values 1 0.6 0.45 0.35 --out variants/ \
      [--size 424x435] [--png]

Finds the single <g> whose id/data-name contains --group (a regex) and sets `opacity` on that group,
not on each child, so overlapping pieces fade as one layer with no seams. Writes <stem>_op<value>.svg
for each value and compare.html showing them at --size (the size the asset is drawn at on the board),
with absolute file:// paths so the images load. --png also writes compare.png when Python Playwright
is installed. The text of the SVG is edited in place, so ids, defs and formatting stay as they were.
"""
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('svg')
    ap.add_argument('--group', required=True, help='regex matched against the id / data-name of one <g>')
    ap.add_argument('--values', nargs='+', type=float, default=[1.0, 0.6, 0.45, 0.35])
    ap.add_argument('--out', default='.')
    ap.add_argument('--size', default=None, help='display size WxH on the board, e.g. 424x435')
    ap.add_argument('--png', action='store_true')
    a = ap.parse_args()

    src = open(a.svg, encoding='utf-8').read()
    tags = [m for m in re.finditer(r'<g\b[^>]*>', src)
            if re.search(r'\b(?:id|data-name)="[^"]*(?:' + a.group + ')[^"]*"', m.group(0))]
    if len(tags) != 1:
        print(f'--group must match exactly one <g>; matched {len(tags)}:', file=sys.stderr)
        for m in tags[:10]:
            print('  ' + m.group(0)[:120], file=sys.stderr)
        return 2
    m = tags[0]
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.svg))[0]
    w, h = (a.size.split('x') if a.size else ('', ''))
    cells = []
    for v in a.values:
        tag = re.sub(r'\sopacity="[^"]*"', '', m.group(0))
        tag = tag[:-1].rstrip('/') + f' opacity="{v:g}"' + ('/>' if tag.endswith('/>') else '>')
        out = os.path.join(a.out, f'{stem}_op{v:g}.svg')
        open(out, 'w', encoding='utf-8').write(src[:m.start()] + tag + src[m.end():])
        size = f' width="{w}" height="{h}"' if w else ''
        cells.append(f'<figure style="margin:0;text-align:center"><img src="file://{os.path.abspath(out)}"{size}>'
                     f'<figcaption>{v:g}</figcaption></figure>')
        print('wrote', out)
    html = ('<!doctype html><meta charset="utf-8"><body style="margin:0;padding:20px;background:#fff;'
            'display:flex;gap:24px;font:20px Arial,sans-serif">' + ''.join(cells) + '</body>')
    cmp_html = os.path.join(a.out, 'compare.html')
    open(cmp_html, 'w', encoding='utf-8').write(html)
    print('wrote', cmp_html)
    if a.png:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print('--png needs Python Playwright; open compare.html instead', file=sys.stderr)
            return 0
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={'width': 400, 'height': 300})
            pg.goto('file://' + os.path.abspath(cmp_html))
            pg.wait_for_timeout(500)
            dims = pg.evaluate('[document.body.scrollWidth, document.body.scrollHeight]')
            pg.set_viewport_size({'width': dims[0], 'height': dims[1]})
            pg.screenshot(path=os.path.join(a.out, 'compare.png'))
            b.close()
        print('wrote', os.path.join(a.out, 'compare.png'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
