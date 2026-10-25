#!/usr/bin/env python3
"""Place labels around a ring (e.g. TCA-cycle intermediates) and print absolute boxes.

Each label sits at angle theta (degrees; 0 = right, 90 = down, screen coordinates) on a
circle of radius R around (cx, cy). Right-side labels start 4 px right of the anchor,
left-side labels end 4 px left of it, near-vertical labels are centred. Widths are
measured with an Arial-metric font, so the boxes fit the text.

  python3 scripts/ring_labels.py --center 1580,646 --radius 174 --size 16 \
      --label "Citrate:-90.5" --label "Isocitrate:-26" --label "α-Ketoglutarate:34" \
      --label "Succinyl-CoA:58" --label "Succinate:90" --label "Fumarate:157" \
      --label "Malate:197" --label "Oxaloacetate:-135.7" --bounds 1320,1840

Pick R = visual ring radius + ~14. --bounds warns when a box leaves [xmin, xmax].
Add --html to print absolutely positioned <div>s ready to paste into an artboard.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_text import text_width  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--center', required=True, help='cx,cy')
    ap.add_argument('--radius', type=float, required=True)
    ap.add_argument('--size', type=float, default=16)
    ap.add_argument('--line-height', type=float)
    ap.add_argument('--gap', type=float, default=4)
    ap.add_argument('--label', action='append', required=True, help='"text:angle"')
    ap.add_argument('--bounds', help='xmin,xmax allowed for boxes')
    ap.add_argument('--html', action='store_true')
    a = ap.parse_args()

    cx, cy = (float(v) for v in a.center.split(','))
    lh = a.line_height or round(a.size * 1.25)
    xmin, xmax = (float(v) for v in a.bounds.split(',')) if a.bounds else (-1e9, 1e9)

    for item in a.label:
        text, ang = item.rsplit(':', 1)
        t = math.radians(float(ang))
        ax, ay = cx + a.radius * math.cos(t), cy + a.radius * math.sin(t)
        w = math.ceil(text_width(text, a.size)) + 2
        c, s = math.cos(t), math.sin(t)
        if abs(c) < 0.2:
            left, align = ax - w / 2, 'center'
        elif c > 0:
            left, align = ax + a.gap, 'left'
        else:
            left, align = ax - a.gap - w, 'right'
        top = ay - lh / 2 + s * lh / 2
        left, top = round(left), round(top)
        flag = '' if xmin <= left and left + w <= xmax else '   <-- outside bounds'
        if a.html:
            print(f'<div style="position: absolute; left: {left}px; top: {top}px; width: {w}px; '
                  f'font-size: {a.size:g}px; line-height: {lh:g}px; text-align: {align}; '
                  f'white-space: nowrap">{text}</div>{flag}')
        else:
            print(f'{text:18s} left {left:5d} top {top:5d} width {w:4d} align {align}{flag}')


if __name__ == '__main__':
    main()
