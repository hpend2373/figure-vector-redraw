#!/usr/bin/env python3
"""Draw a cycle diagram (e.g. the TCA cycle) as N identical curved arrows, one per reaction step.

  python3 ring_arrows.py out.svg --steps 8 --style chain            # heads nest in the next tail (closed ring)
  python3 ring_arrows.py out.svg --steps 8 --style gap --flat       # separate arrows, flat fill, no effects

Every arrow has the same size, colour, border and shadow, so the eye reads "one step = one arrow".
Arrow k runs clockwise from junction k to junction k+1; junction 0 is at the top (-90 deg), where the
first metabolite label sits. Defaults reproduce the light-yellow, warm-bordered input ring of the
Space2 TCA figure (288x285 canvas, body radii 104-122, head flare 97-129).

Style options
  --style chain   tail is a V notch parallel to the previous head, offset by --gap-deg (default 1.6)
  --style gap     tail notch of --notch-deg, arrows separated by --gap-deg (default 3)
  --fill a,b,c    gradient stops tail -> head (one colour = flat fill)
  --border C,W    outline colour and width        --halo C,W,OPACITY   pale line under the border
  --shadow / --no-shadow                          --hilite / --no-hilite   thin white line on the outer edge
  --flat          shortcut: single fill, no halo, no shadow, no highlight
Geometry: --size W,H --centre X,Y --body R_IN,R_OUT --head R_IN,R_OUT --head-deg D
"""
import argparse
import math


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--steps', type=int, default=8)
    ap.add_argument('--style', choices=['chain', 'gap'], default='chain')
    ap.add_argument('--gap-deg', type=float)
    ap.add_argument('--notch-deg', type=float, default=6)
    ap.add_argument('--head-deg', type=float, default=12)
    ap.add_argument('--size', default='288,285'); ap.add_argument('--centre', default='143.5,142.5')
    ap.add_argument('--body', default='104,122'); ap.add_argument('--head', default='97,129')
    ap.add_argument('--fill', default='#fff7de,#fbe9b8,#f5d891')
    ap.add_argument('--border', default='#8a7347,1.6')
    ap.add_argument('--halo', default='#a7a39a,3.4,0.5')
    ap.add_argument('--shadow', dest='shadow', action='store_true', default=True)
    ap.add_argument('--no-shadow', dest='shadow', action='store_false')
    ap.add_argument('--hilite', dest='hilite', action='store_true', default=True)
    ap.add_argument('--no-hilite', dest='hilite', action='store_false')
    ap.add_argument('--flat', action='store_true')
    ap.add_argument('--names', help='comma list of step names for data-name attributes')
    a = ap.parse_args()

    W, H = map(float, a.size.split(',')); CX, CY = map(float, a.centre.split(','))
    RI, RO = map(float, a.body.split(',')); HI, HO = map(float, a.head.split(','))
    RM = (RI + RO) / 2; HEAD = a.head_deg
    GAP = a.gap_deg if a.gap_deg is not None else (1.6 if a.style == 'chain' else 3.0)
    stops = a.fill.split(',')
    if a.flat:
        stops = stops[:1]; a.shadow = a.hilite = False; a.halo = ''
    bc, bw = a.border.split(',')
    P = lambda r, t: (CX + r * math.cos(math.radians(t)), CY + r * math.sin(math.radians(t)))
    f = lambda p: f'{p[0]:.2f} {p[1]:.2f}'
    ang = lambda p: math.degrees(math.atan2(p[1] - CY, p[0] - CX))

    def hit(A, B, r):
        ax, ay = A[0] - CX, A[1] - CY; dx, dy = B[0] - A[0], B[1] - A[1]
        qa = dx * dx + dy * dy; qb = 2 * (ax * dx + ay * dy); qc = ax * ax + ay * ay - r * r
        disc = math.sqrt(max(qb * qb - 4 * qa * qc, 0))
        for t in sorted(((-qb - disc) / (2 * qa), (-qb + disc) / (2 * qa))):
            if -1e-6 <= t <= 1 + 1e-6:
                return (A[0] + t * dx, A[1] + t * dy)
        raise ValueError('notch line misses the body circle; reduce --head-deg or widen --head')

    def arrow(t0, t1):
        if a.style == 'chain':
            tip = t1 - GAP / 2; apex = t0 + GAP / 2; pb = apex - HEAD
            oc = hit(P(HO, pb), P(RM, apex), RO); ic = hit(P(HI, pb), P(RM, apex), RI)
        else:
            tip = t1 - GAP / 2; s0 = t0 + GAP / 2; apex = s0 + a.notch_deg
            oc, ic = P(RO, s0), P(RI, s0)
        hb = tip - HEAD
        d = ' '.join([f'M {f(oc)}', f'A {RO:g} {RO:g} 0 0 1 {f(P(RO, hb))}', f'L {f(P(HO, hb))}', f'L {f(P(RM, tip))}',
                      f'L {f(P(HI, hb))}', f'L {f(P(RI, hb))}', f'A {RI:g} {RI:g} 0 0 0 {f(ic)}', f'L {f(P(RM, apex))}', 'Z'])
        r = RO - 1.6; s, e = ang(oc) + 1.5, hb - 1
        hl = f'M {f(P(r, s))} A {r} {r} 0 0 1 {f(P(r, e))}'
        return d, hl, P(RM, apex), P(RM, tip)

    names = a.names.split(',') if a.names else [f'step {k + 1}' for k in range(a.steps)]
    step = 360 / a.steps
    defs, body = [], []
    if a.shadow:
        defs.append('<filter id="ra-shadow" x="-10%" y="-10%" width="125%" height="125%" color-interpolation-filters="sRGB">'
                    '<feDropShadow dx="1.4" dy="2" stdDeviation="1.5" flood-color="#4a3b1c" flood-opacity="0.3"/></filter>')
    for k in range(a.steps):
        t0 = -90 + step * k
        d, hl, g0, g1 = arrow(t0, t0 + step)
        if len(stops) > 1:
            gid = f'ra-grad-{k + 1}'
            st = ''.join(f'<stop offset="{i / (len(stops) - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(stops))
            defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{g0[0]:.1f}" y1="{g0[1]:.1f}" '
                        f'x2="{g1[0]:.1f}" y2="{g1[1]:.1f}">{st}</linearGradient>')
            fill = f'url(#{gid})'
        else:
            fill = stops[0]
        g = [f'<g data-name="{names[k] if k < len(names) else k + 1}">']
        if a.halo:
            hc, hw, ho = a.halo.split(',')
            g.append(f'<path d="{d}" fill="none" stroke="{hc}" stroke-width="{hw}" stroke-opacity="{ho}" stroke-linejoin="round"/>')
        g.append(f'<path d="{d}" fill="{fill}" stroke="{bc}" stroke-width="{bw}" stroke-linejoin="round"/>')
        if a.hilite:
            g.append(f'<path d="{hl}" fill="none" stroke="#ffffff" stroke-width="1" stroke-opacity="0.75" stroke-linecap="round"/>')
        body.append(''.join(g) + '</g>')
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:g}" height="{H:g}" viewBox="0 0 {W:g} {H:g}">',
           f'<title>Cycle of {a.steps} identical step arrows</title>',
           '<defs>' + ''.join(defs) + '</defs>',
           '<g' + (' filter="url(#ra-shadow)"' if a.shadow else '') + '>', *body, '</g>', '</svg>']
    open(a.out, 'w').write('\n'.join(out))
    print('wrote', a.out, f'({a.steps} arrows, style {a.style}, gap {GAP} deg)')


if __name__ == '__main__':
    main()
