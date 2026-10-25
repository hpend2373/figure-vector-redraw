#!/usr/bin/env python3
"""Remove unwanted elements (e.g. decorative icons) from a RAW traced SVG.

Works on vectorizer output before svgo (absolute M/C/L/Z + translate()). Coordinates
are in the paths' own space: if the body sits in <g transform="scale(0.5)">, give
boxes in 2x pixels.

  --box x0,y0,x1,y1          drop every path (mask and colour layers) whose bbox lies
                             fully inside the box
  --halo-box x0,y0,x1,y1     drop light colour paths (luminance >= --halo-lum) whose bbox
                             centre is in the box and that are smaller than --halo-max
  --mask-ellipse cx,cy,rx,ry paint a black ellipse into the mask (hides what is left)

Example (two icons above graph hubs, then hide their glow):

  python3 scripts/svg_remove_boxes.py gat.svg gat_clean.svg \
      --box 170,72,250,146 --box 444,72,516,146 \
      --halo-box 165,65,255,150 --halo-box 440,65,520,150 \
      --mask-ellipse 210,112,46,33 --mask-ellipse 480,112,34,34

Always render the result (scripts/render.js svg ...) and look at it.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgtools import fill_luminance, raw_path_bbox  # noqa: E402


def quad(s):
    v = [float(x) for x in s.split(',')]
    if len(v) != 4:
        raise argparse.ArgumentTypeError('expected four comma-separated numbers')
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--box', type=quad, action='append', default=[])
    ap.add_argument('--halo-box', type=quad, action='append', default=[])
    ap.add_argument('--halo-lum', type=float, default=180)
    ap.add_argument('--halo-max', type=float, default=140, help='max bbox side for halo removal')
    ap.add_argument('--mask-ellipse', type=quad, action='append', default=[])
    a = ap.parse_args()

    s = open(a.src, encoding='utf-8').read()
    mask_end = s.find('</mask>')
    removed = {'box': 0, 'halo': 0}
    out, last = [], 0
    for m in re.finditer(r'<path\b[^>]*/>\n?', s):
        tag = m.group(0)
        bb = raw_path_bbox(tag)
        drop = False
        if bb:
            x0, y0, x1, y1 = bb
            for bx0, by0, bx1, by1 in a.box:
                if x0 >= bx0 and x1 <= bx1 and y0 >= by0 and y1 <= by1:
                    drop = True
                    removed['box'] += 1
                    break
            if not drop and m.start() > mask_end and a.halo_box:
                lum = fill_luminance(tag)
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                small = (x1 - x0) < a.halo_max and (y1 - y0) < a.halo_max
                for bx0, by0, bx1, by1 in a.halo_box:
                    if lum is not None and lum >= a.halo_lum and small and bx0 <= cx <= bx1 and by0 <= cy <= by1:
                        drop = True
                        removed['halo'] += 1
                        break
        if drop:
            out.append(s[last:m.start()])
            last = m.end()
    out.append(s[last:])
    s = ''.join(out)

    if a.mask_ellipse:
        i = s.find('</mask>')
        j = s.rfind('</g>', 0, i)
        insert_at = j if j != -1 and j > s.rfind('<mask', 0, i) else i
        ell = ''.join(f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}" fill="#000000"/>'
                      for cx, cy, rx, ry in a.mask_ellipse)
        s = s[:insert_at] + ell + s[insert_at:]

    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write(s)
    print(f"removed {removed['box']} box paths, {removed['halo']} halo paths; "
          f"added {len(a.mask_ellipse)} mask ellipses -> {a.out}")


if __name__ == '__main__':
    main()
