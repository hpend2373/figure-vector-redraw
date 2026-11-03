#!/usr/bin/env python3
"""Spread an illustrative UMAP/scatter (SVG of <circle> dots) to fill its card without squashing clusters.

Stretching the picture (scaleY) flattens every cluster. Instead the dots are grouped into spatial islands
(DBSCAN); island centres move apart by KX, KY around the plot centre, each island is scaled only mildly
(SX, SY) and dot radii grow by sqrt(SX*SY) so density stays the same. Labels on the board follow the island
of their nearest dot. The new SVG is written in board coordinates, so its <img> box is set 1:1.

  python3 umap_spread.py board.dc.html umap_src.svg out.svg out.dc.html \
      --img-alt "UMAP of single-cell clusters" \
      --labels "Exc. neuron,Inh. neuron,Astrocyte,Endothelial,Microglia,OPC,Oligodendrocyte" \
      --k 1.02,1.35 --s 1.1,1.15 --bottom 903 --card 52,324

  umap_src.svg  the dot SVG currently placed in that <img> (its viewBox is mapped onto the img box)
  --k KX,KY     island-centre spread (KY 1.3-1.4 matched a neighbouring map; 2.0 read as "too stretched")
  --s SX,SY     island scale (keep <= 1.15 so shapes stay natural)
  --bottom Y    pin the dot box bottom to Y (e.g. the neighbouring panel's image bottom); else --cy Y
  --card X0,X1  card left/right edges; labels are kept >= 12 px inside
  --move G:DX,DY  shift the island holding most dots of group id G (e.g. "violet:-61,6") to free room
                  for a label. Only for ILLUSTRATIVE plots: never move clusters of a real embedding.
  --font FILE   font for label widths (default: Liberation Sans / Arial metrics)
Needs numpy, scikit-learn, Pillow.
"""
import argparse
import os
import re

import numpy as np
from PIL import ImageFont
from sklearn.cluster import DBSCAN


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board'); ap.add_argument('src_svg'); ap.add_argument('out_svg'); ap.add_argument('out_dc')
    ap.add_argument('--img-alt', required=True); ap.add_argument('--labels', required=True)
    ap.add_argument('--k', default='1.0,1.35'); ap.add_argument('--s', default='1.1,1.15')
    ap.add_argument('--bottom', type=float); ap.add_argument('--cy', type=float)
    ap.add_argument('--card'); ap.add_argument('--move', action='append', default=[])
    ap.add_argument('--eps', type=float, default=5.0)
    ap.add_argument('--font', default='/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf')
    a = ap.parse_args()
    KX, KY = map(float, a.k.split(',')); SX, SY = map(float, a.s.split(','))

    s = open(a.src_svg).read(); b = open(a.board, encoding='utf-8').read()
    img = re.search(r'<img src="[^"]+" alt="' + re.escape(a.img_alt) + r'" style="position: absolute; '
                    r'left: ([-\d.]+)px; top: ([-\d.]+)px; width: ([\d.]+)px; height: ([\d.]+)px">', b)
    if not img:
        raise SystemExit('img with that alt not found (expects left/top/width/height inline style)')
    L0, T0, W0, H0 = map(float, img.groups())
    vb = list(map(float, re.search(r'viewBox="([^"]+)"', s).group(1).replace(',', ' ').split()))
    fx, fy = W0 / vb[2], H0 / vb[3]

    circ, grp, stack = [], [], []
    for t in re.finditer(r'<g\b([^>]*)>|</g>|<circle ([^>]*?)/?>', s):   # id of the enclosing <g id=...>
        if t.group(0).startswith('</g'):
            stack and stack.pop()
        elif t.group(0).startswith('<g'):
            gid = re.search(r'id="([^"]+)"', t.group(1) or ''); stack.append(gid.group(1) if gid else '')
        else:
            circ.append(t); grp.append(next((x for x in reversed(stack) if x), ''))
    grp = np.array(grp)
    gv = lambda att, k: float(re.search(rf'(?<![-\w]){k}="([-\d.]+)"', att).group(1))
    P = np.array([(L0 + (gv(c.group(2), 'cx') - vb[0]) * fx, T0 + (gv(c.group(2), 'cy') - vb[1]) * fy) for c in circ])
    R = np.array([gv(c.group(2), 'r') * fx for c in circ])
    lab = DBSCAN(eps=a.eps, min_samples=4).fit(P).labels_
    core = lab >= 0
    for i in np.where(~core)[0]:
        lab[i] = lab[np.argmin(np.where(core, np.hypot(*(P - P[i]).T), np.inf))]
    cen = {k: P[lab == k].mean(0) for k in set(lab)}
    C = P.mean(0)
    shift = {k: np.zeros(2) for k in cen}
    for mv in a.move:
        g, d = mv.split(':'); dx, dy = map(float, d.split(','))
        sel = np.array([g in x for x in grp])
        k = max(set(lab[sel]), key=lambda q: (sel & (lab == q)).sum())
        shift[k] = np.array([dx, dy])
    rad = R * (SX * SY) ** 0.5
    cy_t = a.cy if a.cy is not None else C[1]

    def T(k, p):
        c = cen[k]
        return np.array([C[0] + (c[0] - C[0]) * KX, cy_t + (c[1] - C[1]) * KY]) + (p - c) * [SX, SY] + shift[k]

    for _ in range(2):
        NP = np.array([T(lab[i], P[i]) for i in range(len(P))])
        x0, y0 = (NP - rad[:, None]).min(0) - 2; x1, y1 = (NP + rad[:, None]).max(0) + 2
        if a.bottom is None:
            break
        cy_t += a.bottom - y1

    out, last = [], 0
    for i, c in enumerate(circ):
        att = re.sub(r'(?<![-\w])cx="[-\d.]+"', f'cx="{NP[i, 0]:.2f}"', c.group(2))
        att = re.sub(r'(?<![-\w])cy="[-\d.]+"', f'cy="{NP[i, 1]:.2f}"', att)
        att = re.sub(r'(?<![-\w])r="[\d.]+"', f'r="{rad[i]:.2f}"', att)
        out += [s[last:c.start()], f'<circle {att.rstrip("/").rstrip()}/>']; last = c.end()
    out.append(s[last:]); s2 = ''.join(out)
    s2 = re.sub(r'(<svg[^>]*?)width="[^"]*"', rf'\1width="{x1 - x0:.1f}"', s2, count=1)
    s2 = re.sub(r'(<svg[^>]*?)height="[^"]*"', rf'\1height="{y1 - y0:.1f}"', s2, count=1)
    s2 = re.sub(r'viewBox="[^"]+"', f'viewBox="{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}"', s2, count=1)
    open(a.out_svg, 'w').write(s2)

    fnt = ImageFont.truetype(a.font, 80) if os.path.exists(a.font) else None
    num = lambda st, k: float(re.search(rf'(?<![-\w]){k}: ([-\d.]+)px', st).group(1))
    for name in [n.strip() for n in a.labels.split(',') if n.strip()]:
        m = re.search(r'<div style="([^"]*)">' + re.escape(name) + '</div>', b)
        if not m:
            print('  label not found:', name); continue
        st = m.group(1); lx, ly, lw = num(st, 'left'), num(st, 'top'), num(st, 'width')
        lh = num(st, 'line-height'); bc = np.array([lx + lw / 2, ly + lh / 2])
        j = np.argmin(np.hypot(*(P - bc).T)); d = T(lab[j], bc) - bc
        nx, ny = lx + d[0], ly + d[1]
        if a.card and fnt:
            c0, c1 = map(float, a.card.split(',')); fs = num(st, 'font-size')
            tw = fnt.getlength(name) / 80 * fs
            il = nx + (lw - tw) / 2
            nx += max(0, c0 + 12 - il) - max(0, il + tw - (c1 - 12))
        st2 = re.sub(r'(?<![-\w])left: [-\d.]+px', f'left: {round(nx, 1):g}px', st, count=1)
        st2 = re.sub(r'(?<![-\w])top: [-\d.]+px', f'top: {round(ny, 1):g}px', st2, count=1)
        b = b.replace(m.group(0), f'<div style="{st2}">{name}</div>')
        print(f'  {name:18} -> ({nx:.1f}, {ny:.1f})')
    b = b.replace(img.group(0), img.group(0).split(' style=')[0] +
                  f' style="position: absolute; left: {x0:.1f}px; top: {y0:.1f}px; width: {x1 - x0:.1f}px; height: {y1 - y0:.1f}px">')
    open(a.out_dc, 'w', encoding='utf-8').write(b)
    print(f'islands {len(cen)}, dot box {x0:.1f},{y0:.1f} - {x1:.1f},{y1:.1f}; check label/dot overlaps in a render')


if __name__ == '__main__':
    main()
