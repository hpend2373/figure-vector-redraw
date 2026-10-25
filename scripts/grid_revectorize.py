#!/usr/bin/env python3
"""Re-vectorise a pixel-grid image (e.g. a spatial-transcriptomics spot map) as compact
run-length rectangles, instead of shipping a heavy trace.

Input is a PNG render of the map on a white background (render the traced SVG with
scripts/render.js at 2x). Each output cell is `--cell` pixels of the PNG; the median
colour of the cell is used, so spot colours stay crisp. One <path> per colour holds
`M x y h w v1 h-w z` runs; viewBox units are cells. Typical result: 10+ MB -> < 0.4 MB.

Faithful copy (quantised to --colors colours):
  python3 scripts/grid_revectorize.py map@2x.png st_input.svg --cell 2

Repair an artefact (e.g. a white notch) by vertical interpolation inside a cell box:
  python3 scripts/grid_revectorize.py map@2x.png st_input.svg --cell 2 --fix 199,104,215,117

Derived, ILLUSTRATIVE intensity maps (label them as illustrative in the figure):
  python3 scripts/grid_revectorize.py map@2x.png st_neuron.svg --cell 2 \
      --ramp "#fdf0ed,#f16555,#a8241b" --blur 1.6
  python3 scripts/grid_revectorize.py map@2x.png st_astro.svg --cell 2 \
      --ramp "#eef4fa,#4986b9,#1d4a7a" --invert --blur 3 --gamma 1.6
"""
import argparse

import numpy as np
from PIL import Image, ImageFilter

LUM = np.array([0.299, 0.587, 0.114])


def hex_rgb(h):
    h = h.strip().lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def to_hex(c):
    return '#%02x%02x%02x' % tuple(int(round(v)) for v in c)


def write_svg(path, colors, mask):
    gh, gw = mask.shape
    groups = {}
    for y in range(gh):
        x = 0
        while x < gw:
            if not mask[y, x]:
                x += 1
                continue
            c, x0 = colors[y][x], x
            while x < gw and mask[y, x] and colors[y][x] == c:
                x += 1
            groups.setdefault(c, []).append(f'M{x0} {y}h{x - x0}v1h-{x - x0}z')
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{gw}" height="{gh}" '
             f'viewBox="0 0 {gw} {gh}" shape-rendering="crispEdges">']
    lines += [f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in groups.items()]
    lines.append('</svg>')
    s = '\n'.join(lines)
    with open(path, 'w') as fh:
        fh.write(s)
    print(f'{path}: {gw}x{gh} cells, {len(groups)} colours, {len(s)} bytes')


def blur(arr, sigma, weight):
    if sigma <= 0:
        return arr
    im = Image.fromarray((np.clip(arr * weight, 0, 1) * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(sigma))
    wm = Image.fromarray((weight * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(sigma))
    return np.clip(np.asarray(im, float) / np.maximum(np.asarray(wm, float), 1), 0, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('png')
    ap.add_argument('out')
    ap.add_argument('--cell', type=int, default=2, help='PNG pixels per output cell')
    ap.add_argument('--bg-lum', type=float, default=238, help='cells brighter than this are background')
    ap.add_argument('--colors', type=int, default=48)
    ap.add_argument('--fix', action='append', default=[], help='x0,y0,x1,y1 in cells: interpolate bright cells vertically')
    ap.add_argument('--ramp', help='comma-separated low,mid,high colours -> derived intensity map')
    ap.add_argument('--invert', action='store_true')
    ap.add_argument('--blur', type=float, default=0.0)
    ap.add_argument('--gamma', type=float, default=1.0)
    ap.add_argument('--levels', type=int, default=12)
    a = ap.parse_args()

    img = np.asarray(Image.open(a.png).convert('RGB'), float)
    cs = a.cell
    gh, gw = img.shape[0] // cs, img.shape[1] // cs
    cells = np.median(img[:gh * cs, :gw * cs].reshape(gh, cs, gw, cs, 3), axis=(1, 3))
    lum = cells @ LUM

    for box in a.fix:
        x0, y0, x1, y1 = (int(v) for v in box.split(','))
        for x in range(x0, min(x1, gw)):
            for y in range(y0, min(y1, gh)):
                if lum[y, x] > 170:
                    up = next((yy for yy in range(y - 1, -1, -1) if lum[yy, x] < 160), None)
                    dn = next((yy for yy in range(y + 1, gh) if lum[yy, x] < 160), None)
                    if up is not None and dn is not None and dn - up < 40:
                        f = (y - up) / (dn - up)
                        cells[y, x] = cells[up, x] * (1 - f) + cells[dn, x] * f
        lum = cells @ LUM

    tissue = lum < a.bg_lum

    if not a.ramp:
        q = Image.fromarray(np.clip(cells, 0, 255).astype('uint8')).quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT)
        pal = np.array(q.getpalette()[:3 * a.colors]).reshape(-1, 3)
        idx = np.asarray(q)
        colors = [[to_hex(pal[idx[y, x]]) for x in range(gw)] for y in range(gh)]
        write_svg(a.out, colors, tissue)
        return

    inner = np.asarray(Image.fromarray((tissue * 255).astype('uint8')).filter(ImageFilter.MinFilter(7))) > 127
    vals = lum[inner] if inner.any() else lum[tissue]
    lo, hi = np.percentile(vals, 3), np.percentile(vals, 97)
    v = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)
    if a.invert:
        v = 1 - v
    w = inner.astype(float)
    core = blur(v, a.blur, w)
    edge = blur(v, max(a.blur, 1) * 2.5, w)
    v = np.where(inner, core, edge)
    tv = v[tissue]
    lo, hi = np.percentile(tv, 2), np.percentile(tv, 98)
    v = np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1) ** a.gamma

    stops = [hex_rgb(c) for c in a.ramp.split(',')]
    pos = np.linspace(0, 1, len(stops))

    def ramp(x):
        for k in range(len(stops) - 1):
            if x <= pos[k + 1]:
                f = (x - pos[k]) / (pos[k + 1] - pos[k])
                return stops[k] + (stops[k + 1] - stops[k]) * f
        return stops[-1]

    lv = np.minimum((v * a.levels).astype(int), a.levels - 1)
    colors = [[to_hex(ramp((lv[y, x] + 0.5) / a.levels)) for x in range(gw)] for y in range(gh)]
    write_svg(a.out, colors, tissue)


if __name__ == '__main__':
    main()
