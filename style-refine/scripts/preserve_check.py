#!/usr/bin/env python3
"""Compare two versions of a figure (SVG or HTML artboard) for content that a style pass must keep.

Checks: every text string (as a multiset), the count of drawn shapes by kind, arrow markers /
arrow-like polygons, and the set of colours used inside data/diagram art (nested <svg> blocks or
groups matching --art). Prints what was added or lost; exit code 1 when something changed.

  python3 preserve_check.py before.svg after.svg [--art "umap|network|gat"] [--ignore-faint 0.3]

--ignore-faint T leaves shapes whose own opacity is below T (glows, halos, soft shadows drawn as
separate faint shapes) out of the art counts, so flattening those effects is not reported as lost data.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

SHAPES = ('path', 'line', 'polyline', 'polygon', 'rect', 'circle', 'ellipse', 'image', 'use')


def texts_html(src):
    body = re.sub(r'<svg\b.*?</svg>', '', src, flags=re.S)
    out = []
    for m in re.finditer(r'<div\b[^>]*>(.*?)</div>', body, flags=re.S):
        t = re.sub(r'<br\s*/?>', ' ', m.group(1)); t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        if t:
            out.append(t)
    return out


def load(path, art_re, faint=0.0):
    src = open(path, encoding='utf-8').read()
    texts, shapes, art_colours, arrows = Counter(), Counter(), Counter(), 0
    roots = []
    if path.lower().endswith('.svg'):
        roots = [ET.fromstring(src.encode('utf-8'))]
    else:
        for t in texts_html(src):
            texts[t] += 1
        roots = [ET.fromstring(m.group(0)) for m in re.finditer(r'<svg\b.*?</svg>', src, flags=re.S)]
        imgs = re.findall(r'<img\b[^>]*src="([^"]+)"', src) + re.findall(r'background-image:url\(([^)]+)\)', src)
        shapes['embedded-image'] += len(imgs)

    def walk(el, in_art, top):
        nonlocal arrows
        tag = el.tag.split('}')[-1]
        ident = ' '.join(filter(None, [el.get('id'), el.get('data-name'), el.get('class')]))
        if not top and (tag == 'svg' or (art_re and ident and re.search(art_re, ident))):
            in_art = True
        if tag == 'text':
            t = re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()
            if t:
                texts[t] += 1
        try:
            op = float(el.get('opacity', '1'))
        except ValueError:
            op = 1.0
        if faint and in_art and op < faint and tag in SHAPES:
            for c in el:
                walk(c, in_art, False)
            return
        if tag in SHAPES:
            shapes[('art:' if in_art else 'frame:') + tag] += 1
        if tag == 'marker' or (tag == 'polygon' and len(re.findall(r'[-\d.]+', el.get('points', ''))) in (6, 8)):
            arrows += 1
        if in_art:
            for k in ('fill', 'stroke'):
                v = (el.get(k) or '').lower()
                m = re.search(r'#[0-9a-f]{6}|#[0-9a-f]{3}\b', v + ' ' + (el.get('style') or '').lower())
                if m:
                    art_colours[m.group(0)] += 1
        for c in el:
            walk(c, in_art, False)

    for r in roots:
        walk(r, False, True)
    return dict(texts=texts, shapes=shapes, art_colours=art_colours, arrows=arrows)


def diff(name, a, b):
    lost, added = a - b, b - a
    lines = []
    if lost:
        lines.append(f'  - {name} 빠짐: ' + ', '.join(f'{k}×{v}' for k, v in lost.most_common(20)))
    if added:
        lines.append(f'  + {name} 추가: ' + ', '.join(f'{k}×{v}' for k, v in added.most_common(20)))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('before'); ap.add_argument('after'); ap.add_argument('--art')
    ap.add_argument('--ignore-faint', type=float, default=0.0, help='skip art shapes with opacity below this')
    a = ap.parse_args()
    A, B = load(a.before, a.art, a.ignore_faint), load(a.after, a.art, a.ignore_faint)
    out = []
    out += diff('글자', A['texts'], B['texts'])
    art_a = Counter({k: v for k, v in A['shapes'].items() if not k.startswith('frame:')})
    art_b = Counter({k: v for k, v in B['shapes'].items() if not k.startswith('frame:')})
    out += diff('도식·데이터 도형', art_a, art_b)
    out += diff('도식 안 색', A['art_colours'], B['art_colours'])
    if A['arrows'] != B['arrows']:
        out.append(f'  ! 화살촉 후보 수 {A["arrows"]} → {B["arrows"]}')
    frame = lambda d: Counter({k: v for k, v in d['shapes'].items() if k.startswith('frame:')})
    fd = diff('틀·장식 도형(바뀌어도 됨)', frame(A), frame(B))
    print(f'글자 {sum(A["texts"].values())} → {sum(B["texts"].values())}, 도식 도형 {sum(art_a.values())} → {sum(art_b.values())}')
    if out:
        print('내용 변경 의심:'); print('\n'.join(out))
    else:
        print('글자·도식 도형·도식 색·화살촉 수: 변경 없음')
    if fd:
        print('참고(스타일 변경 범위):'); print('\n'.join(fd))
    return 1 if out else 0


if __name__ == '__main__':
    sys.exit(main())
