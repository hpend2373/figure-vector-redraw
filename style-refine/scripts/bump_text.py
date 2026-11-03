#!/usr/bin/env python3
"""Enlarge text by role on a Design artboard while keeping every position the user chose.

Each text box keeps its anchor: centred labels keep their centre, right-aligned labels their right edge,
left-aligned labels their left edge; labels listed under "keep_vcentre" also keep their vertical centre.
Boxes widen to the new text width measured with the board's own font. Only boxes whose current size equals
the role's old size are touched, so running it twice does nothing.

  python3 bump_text.py in.dc.html out.dc.html roles.json --font-regular R.ttf --font-bold B.ttf

roles.json:
  {"roles": {"Citrate": [22, 23, 29], "Graph attention network (GAT)": [26, 28, 34]},   # text: [old, new, line-height]
   "keep_vcentre": ["Citrate"]}
Texts with <br> are matched as written in the file (e.g. "Spatial<br>transcriptomics").
Afterwards re-check labels that sit next to lines or card edges (render and look).
"""
import argparse
import json
import re

from PIL import ImageFont


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('roles')
    ap.add_argument('--font-regular', required=True); ap.add_argument('--font-bold', required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.roles, encoding='utf-8'))
    roles, vc = cfg['roles'], set(cfg.get('keep_vcentre', []))
    fonts = {}

    def tw(text, size, bold):
        k = (size, bold)
        if k not in fonts:
            fonts[k] = ImageFont.truetype(a.font_bold if bold else a.font_regular, size * 4)
        return max(fonts[k].getlength(t) for t in text.split('\n')) / 4

    num = lambda st, k: float(re.search(rf'(?<![-\w]){k}: ([-\d.]+)px', st).group(1))
    fmt = lambda v: f'{round(v, 1):g}'
    s = open(a.src, encoding='utf-8').read()
    done = []

    def bump(m):
        st, inner = m.group(1), m.group(2)
        if inner not in roles:
            return m.group(0)
        old, new, lh = roles[inner]
        if f'font-size: {old}px' not in st:
            return m.group(0)
        bold = 'font-weight: 700' in st or 'font-weight: bold' in st
        plain = re.sub(r'<br\s*/?>', '\n', re.sub(r'<(?!br)[^>]+>', '', inner)).replace('&amp;', '&')
        n = plain.count('\n') + 1
        left, top, width = num(st, 'left'), num(st, 'top'), num(st, 'width')
        lh_old = num(st, 'line-height')
        al = re.search(r'text-align: (\w+)', st); al = al.group(1) if al else 'left'
        new_w = max(width, tw(plain, new, bold) + (4 if al in ('left', 'start') else 2))
        if al in ('right', 'end'):
            left += width - new_w
        elif al == 'center':
            left += (width - new_w) / 2
        if inner in vc:
            top -= (lh - lh_old) * n / 2
        st2 = re.sub(r'font-size: [\d.]+px', f'font-size: {new}px', st)
        st2 = re.sub(r'line-height: [\d.]+px', f'line-height: {lh}px', st2)
        for k, v in (('left', left), ('top', top), ('width', new_w)):
            st2 = re.sub(rf'(?<![-\w]){k}: [-\d.]+px', f'{k}: {fmt(v)}px', st2, count=1)
        if re.search(r'(?<![-\w])height: [\d.]+px', st2):
            st2 = re.sub(r'(?<![-\w])height: [\d.]+px', f'height: {lh * n + 1}px', st2, count=1)
        done.append((plain.replace('\n', ' ')[:32], old, new))
        return f'<div style="{st2}">{inner}</div>'

    s = re.sub(r'<div style="([^"]*)">((?:(?!<div\b)(?!</div>).)*?)</div>', bump, s, flags=re.S)
    open(a.dst, 'w', encoding='utf-8').write(s)
    print(len(done), 'text boxes enlarged')
    for d in done:
        print('  ', d)


if __name__ == '__main__':
    main()
