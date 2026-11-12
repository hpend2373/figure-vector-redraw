#!/usr/bin/env python3
"""Put every label around a ring diagram at the same ink gap from the ring (Design .dc.html artboard).

The script renders the artboard twice with Chromium (ring only / labels only), builds a distance map
from the ring's ink and moves each label until its nearest ink pixel is exactly --gap px from the ring.
Text, size and colour are untouched; only `left`/`top` change (nested, card-relative labels work too).

  python3 ring_label_gap.py board.dc.html blobs.json out.dc.html \
      --ring-alt "TCA cycle schematic" --labels "Citrate,Isocitrate,α-Ketoglutarate,Succinyl-CoA,Succinate,Fumarate,Malate,Oxaloacetate" \
      --region 60,170,600,480 --gap 16 --rule axes

  --ring-alt / --ring-class   the ring element: an <img alt="..."> or an element with that class
  --width / --height          artboard dimensions in CSS pixels (default 1920 × 1080)
  --region x0,y0,x1,y1        board box that holds the ring and its labels (labels outside it are ignored,
                              so two rings with the same label names can be handled one at a time)
  --centre cx,cy              ring centre; default = centre of the ring ink's bounding box. Pass the true
                              geometric centre when arrowheads make the ink box lopsided.
  --rule radial               move each label along centre -> label (irregular rings)
  --rule axes                 regular rings: top/bottom labels centred on cx and moved vertically,
                              left/right labels centred on cy and moved horizontally, mirrored diagonal
                              pairs share one y and move horizontally
blobs.json maps /_blob/<id> -> local file (same map as dc_preview.py). Needs numpy, scipy, Pillow, playwright.
Rasterisation noise is about +-0.7 px at 2x; one pass is enough.
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy import ndimage

S = 2  # render scale


def localise(src, blobs):
    m = json.load(open(blobs))
    base = os.path.dirname(os.path.abspath(blobs))
    miss = sorted({i for i in re.findall(r'/_blob/([0-9a-f]{32})', src) if i not in m})
    if miss:
        sys.exit('missing blobs: ' + ', '.join(miss))
    src = re.sub(r'/_blob/([0-9a-f]{32})', lambda g: 'file://' + os.path.abspath(os.path.join(base, m[g.group(1)])), src)
    src = src.replace('<script src="./support.js"></script>', '')
    src = re.sub(r'<script type="text/x-dc".*?</script>', '', src, flags=re.S)
    for t in ('<x-dc>', '</x-dc>', '<helmet>', '</helmet>'):
        src = src.replace(t, '')
    return src


def render(html, extra_css, page):
    """Load the page from a temp file (file:// assets need a file:// origin) and screenshot it."""
    f = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
    f.write(html.replace('</head>', f'<style>{extra_css}</style></head>') if '</head>' in html
            else f'<style>{extra_css}</style>' + html)
    f.close()
    page.goto('file://' + f.name); page.wait_for_timeout(600)
    png = tempfile.NamedTemporaryFile(suffix='.png', delete=False); png.close()
    page.screenshot(path=png.name)
    return np.asarray(Image.open(png.name).convert('L')).astype(float)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('blobs'); ap.add_argument('out')
    ap.add_argument('--labels', required=True); ap.add_argument('--region', required=True)
    ap.add_argument('--width', type=int, default=1920, help='artboard width in CSS pixels')
    ap.add_argument('--height', type=int, default=1080, help='artboard height in CSS pixels')
    ap.add_argument('--ring-alt'); ap.add_argument('--ring-class')
    ap.add_argument('--centre'); ap.add_argument('--gap', type=float, default=16)
    ap.add_argument('--rule', choices=['radial', 'axes'], default='radial')
    ap.add_argument('--ink', type=float, default=200, help='grey level below which a ring pixel counts as ink (0-255)')
    a = ap.parse_args()
    if a.width < 1 or a.height < 1:
        ap.error('--width and --height must be positive')
    from playwright.sync_api import sync_playwright

    src = open(a.src, encoding='utf-8').read()
    names = [n.strip() for n in a.labels.split(',') if n.strip()]
    x0, y0, x1, y1 = map(float, a.region.split(','))

    # tag candidate label divs with data-lg so the browser can report their boxes
    tagged, spans, k = [], [], 0
    pat = re.compile(r'<div style="([^"]*)">(' + '|'.join(map(re.escape, names)) + r')</div>')
    last = 0
    for m in pat.finditer(src):
        tagged.append(src[last:m.start()]); tagged.append(f'<div data-lg="{k}" style="{m.group(1)}">{m.group(2)}</div>')
        spans.append((m.start(), m.end(), m.group(1), m.group(2))); last = m.end(); k += 1
    tagged.append(src[last:]); tagged = ''.join(tagged)
    if a.ring_alt:
        tagged = tagged.replace(f'alt="{a.ring_alt}"', f'alt="{a.ring_alt}" data-ring="1"', 1)
    elif a.ring_class:
        tagged = tagged.replace(f'class="{a.ring_class}"', f'class="{a.ring_class}" data-ring="1"', 1)
    else:
        sys.exit('give --ring-alt or --ring-class')
    html = localise(tagged, a.blobs)

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': a.width, 'height': a.height}, device_scale_factor=S)
        hide = 'body *{visibility:hidden !important}'
        ring = render(html, hide + '[data-ring],[data-ring] *{visibility:visible !important}', page)
        labs = render(html, hide + '[data-lg]{visibility:visible !important}', page)
        render(html, '', page)
        rects = page.evaluate('''() => [...document.querySelectorAll('[data-lg]')].map(e => {
            const r = e.getBoundingClientRect(); return [+e.dataset.lg, r.x, r.y, r.width, r.height]; })''')
        b.close()

    X0, Y0, X1, Y1 = (int(v * S) for v in (x0, y0, x1, y1))
    ink = np.zeros_like(ring, dtype=bool); ink[Y0:Y1, X0:X1] = ring[Y0:Y1, X0:X1] < a.ink
    if not ink.any():
        sys.exit('no ring ink inside --region')
    yy, xx = np.nonzero(ink)
    if a.centre:
        cx, cy = map(float, a.centre.split(','))
    else:
        cx, cy = (xx.min() + xx.max()) / 2 / S, (yy.min() + yy.max()) / 2 / S
    dt = ndimage.distance_transform_edt(~ink) / S

    L = []
    for i, rx, ry, rw, rh in rects:
        if not (x0 <= rx + rw / 2 <= x1 and y0 <= ry + rh / 2 <= y1):
            continue
        sub = labs[int(ry * S) - 2:int((ry + rh) * S) + 2, int(rx * S) - 2:int((rx + rw) * S) + 2] < 128
        ly, lx = np.nonzero(sub)
        if not len(lx):
            continue
        pts = np.stack([lx + int(rx * S) - 2, ly + int(ry * S) - 2], 1)
        ink_c = ((pts[:, 0].min() + pts[:, 0].max()) / 2 / S, (pts[:, 1].min() + pts[:, 1].max()) / 2 / S)
        L.append(dict(i=i, text=spans[i][3], pts=pts, box=(rx, ry, rw, rh), c=ink_c,
                      ang=math.degrees(math.atan2(ink_c[1] - cy, ink_c[0] - cx))))

    H, W = dt.shape

    def gap(l, dx, dy):
        q = np.round(l['pts'] + [dx * S, dy * S]).astype(int)
        q[:, 0] = q[:, 0].clip(0, W - 1); q[:, 1] = q[:, 1].clip(0, H - 1)
        return float(dt[q[:, 1], q[:, 0]].min())

    def solve(l, ux, uy, dx0=0.0, dy0=0.0):
        ts = [t for t in np.arange(-40, 40.01, 0.1) if gap(l, dx0 + ux * t, dy0 + uy * t) >= a.gap]
        t = min(ts) if ts else 0.0
        return dx0 + ux * t, dy0 + uy * t

    moves = {}
    if a.rule == 'radial':
        for l in L:
            vx, vy = l['c'][0] - cx, l['c'][1] - cy; n = math.hypot(vx, vy) or 1
            moves[l['i']] = solve(l, vx / n, vy / n)
    else:
        diag = []
        for l in L:
            t = l['ang']; rx, ry, rw, rh = l['box']
            if abs(t + 90) < 15 or abs(t - 90) < 15:
                moves[l['i']] = solve(l, 0, 1 if t > 0 else -1, cx - (rx + rw / 2), 0)
            elif abs(t) < 15 or abs(t) > 165:
                moves[l['i']] = solve(l, 1 if abs(t) < 90 else -1, 0, 0, cy - (ry + rh / 2))
            else:
                diag.append(l)
        used = set()
        for l in diag:
            if l['i'] in used:
                continue
            mate = min((m for m in diag if m['i'] != l['i'] and m['i'] not in used),
                       key=lambda m: abs(((180 - m['ang']) - l['ang'] + 180) % 360 - 180), default=None)
            pair = [l] + ([mate] if mate and abs(((180 - mate['ang']) - l['ang'] + 180) % 360 - 180) < 15 else [])
            first = {}
            for q in pair:
                sx = 1 if abs(q['ang']) < 90 else -1; sy = 1 if q['ang'] > 0 else -1
                first[q['i']] = solve(q, sx / math.sqrt(2), sy / math.sqrt(2))
            ytop = sum(q['box'][1] + first[q['i']][1] for q in pair) / len(pair)
            for q in pair:
                sx = 1 if abs(q['ang']) < 90 else -1
                moves[q['i']] = solve(q, sx, 0, first[q['i']][0], ytop - q['box'][1])
                used.add(q['i'])

    out, last = [], 0
    num = lambda st, k: float(re.search(rf'(?<![-\w]){k}: ([-\d.]+)px', st).group(1))
    fmt = lambda v: f'{round(v, 1):g}'
    for i, (s0, s1, st, text) in enumerate(spans):
        out.append(src[last:s0]); last = s1
        if i in moves:
            dx, dy = moves[i]
            st = re.sub(r'(?<![-\w])left: [-\d.]+px', f'left: {fmt(num(st, "left") + dx)}px', st, count=1)
            st = re.sub(r'(?<![-\w])top: [-\d.]+px', f'top: {fmt(num(st, "top") + dy)}px', st, count=1)
        out.append(f'<div style="{st}">{text}</div>')
    out.append(src[last:])
    open(a.out, 'w', encoding='utf-8').write(''.join(out))
    print(f'ring centre ({cx:.1f}, {cy:.1f}), target gap {a.gap}px, rule {a.rule}')
    for l in L:
        dx, dy = moves.get(l['i'], (0, 0))
        print(f"  {l['text']:18} angle {l['ang']:7.1f}  gap {gap(l, 0, 0):5.1f} -> {gap(l, dx, dy):5.1f}  move ({dx:+.1f}, {dy:+.1f})")


if __name__ == '__main__':
    main()
