#!/usr/bin/env python3
"""Switch the typeface of an HTML/.dc.html artboard or SVG, and measure what the switch does to text widths.

  # 1) add @font-face rules and put the new family first in every font-family (old list kept as fallback)
  python3 swap_font.py apply in.dc.html out.dc.html --family "NanumBarunGothic" \
      --face 400=/_blob/<regular-woff2-id> --face 700=/_blob/<bold-woff2-id>

  # 2) compare text widths, old font vs new font (needs Pillow); flags boxes the new text overflows
  python3 swap_font.py measure out.dc.html --old LiberationSans-Regular.ttf LiberationSans-Bold.ttf \
      --new NanumBarunGothic.ttf NanumBarunGothicBold.ttf [--min-delta 3]

`apply` uses only the standard library. Faces get font-display:block so the fallback never flashes in.
`measure` reads <div> text with an inline font-size (and SVG <text> with a font-size attribute), picks the
bold file for font-weight >= 600, and lists every line whose width changes by --min-delta px or more, plus
nowrap boxes whose set width is now too small. Use the result to re-place anchored labels and re-fit
rings/cards that were sized from text widths.
"""
import argparse
import re
import sys


def cmd_apply(a):
    s = open(a.src, encoding='utf-8').read()
    fam = a.family
    q = f"'{fam}'"
    faces = []
    for f in a.face:
        w, url = f.split('=', 1)
        fmt = 'woff2' if url.endswith('woff2') or '/_blob/' in url else url.rsplit('.', 1)[-1]
        faces.append(f"@font-face{{font-family:{q};src:url({url}) format('{fmt}');"
                     f"font-weight:{w};font-style:normal;font-display:block}}")
    block = '\n'.join(faces) + '\n'
    if faces and q + ';src' not in s:
        m = re.search(r'<style[^>]*>\n?', s)
        if m:
            s = s[:m.end()] + block + s[m.end():]
        elif '<svg' in s:  # bare SVG: add a <style> right after the root tag
            m = re.search(r'<svg\b[^>]*>', s)
            s = s[:m.end()] + '<defs><style>\n' + block + '</style></defs>' + s[m.end():]
        else:
            sys.exit('no <style> or <svg> to attach @font-face to')
    n = 0

    def css(m):
        nonlocal n
        val = m.group(2).strip()
        if val.lstrip('\'"').startswith(fam):
            return m.group(0)
        n += 1
        return f'{m.group(1)}{q}, {val}'

    s = re.sub(r'(font-family\s*:\s*)([^;"}]+)', css, s)

    def attr(m):
        nonlocal n
        val = m.group(2)
        if val.lstrip('\'"').startswith(fam):
            return m.group(0)
        n += 1
        return f'{m.group(1)}{q}, {val}"'

    s = re.sub(r'(font-family=")([^"]*)"', attr, s)
    open(a.dst, 'w', encoding='utf-8').write(s)
    print(f'@font-face {len(faces)}개 추가, font-family {n}곳 변경 → {a.dst}')


def items(src):
    """(label, size, bold, lines, box_width or None, nowrap) for each text element."""
    out = []
    body = re.sub(r'<(script|style)\b.*?</\1>', '', src, flags=re.S)
    for m in re.finditer(r'<div\b[^>]*style="([^"]*)"[^>]*>((?:(?!<div\b).)*?)</div>', body, flags=re.S):
        st, inner = m.group(1), m.group(2)
        fs = re.search(r'font-size:\s*([\d.]+)px', st)
        if not fs:
            continue
        lines = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()
                 for t in re.split(r'<br\s*/?>', inner)]
        lines = [t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') for t in lines if t]
        if not lines:
            continue
        fw = re.search(r'font-weight:\s*(\d+|bold)', st)
        bold = bool(fw) and (fw.group(1) == 'bold' or int(fw.group(1)) >= 600)
        w = re.search(r'(?<![-\w])width:\s*([\d.]+)px', st)
        out.append((lines[0][:40], float(fs.group(1)), bold, lines,
                    float(w.group(1)) if w else None, 'nowrap' in st))
    for m in re.finditer(r'<text\b([^>]*)>(.*?)</text>', body, flags=re.S):
        at = m.group(1)
        fs = re.search(r'font-size="([\d.]+)', at) or re.search(r'font-size:\s*([\d.]+)', at)
        t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group(2))).strip()
        if fs and t:
            bold = bool(re.search(r'font-weight[=:]\s*"?(bold|[6-9]00)', at))
            out.append((t[:40], float(fs.group(1)), bold, [t], None, True))
    return out


def cmd_measure(a):
    try:
        from PIL import ImageFont
    except ImportError:
        sys.exit('measure needs Pillow: pip install pillow')
    cache = {}

    def width(path, size, text):
        key = (path, size)
        if key not in cache:
            cache[key] = ImageFont.truetype(path, int(round(size * 4)))  # 4x for sub-pixel accuracy
        return cache[key].getlength(text) / 4

    src = open(a.file, encoding='utf-8').read()
    rows, over = [], []
    for label, size, bold, lines, box, nowrap in items(src):
        o = max(width(a.old[1 if bold else 0], size, t) for t in lines)
        n = max(width(a.new[1 if bold else 0], size, t) for t in lines)
        if abs(n - o) >= a.min_delta:
            rows.append((n - o, label, size, bold, o, n))
        if box and nowrap and n > box + 0.5:
            over.append((label, size, box, n))
    rows.sort(key=lambda r: -abs(r[0]))
    print(f'폭 변화 {a.min_delta}px 이상: {len(rows)}개')
    for d, label, size, bold, o, n in rows:
        print(f'  {d:+6.1f}px  {size:g}{"b" if bold else ""}  {o:6.1f} → {n:6.1f}  {label}')
    print(f'nowrap 상자 넘침: {len(over)}개')
    for label, size, box, n in over:
        print(f'  {label}  ({size:g}px)  상자 {box:g} < 글자 {n:.1f}')
    return 1 if over else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('apply')
    p.add_argument('src'); p.add_argument('dst'); p.add_argument('--family', required=True)
    p.add_argument('--face', action='append', default=[], help='WEIGHT=URL, e.g. 400=/_blob/abc')
    p = sub.add_parser('measure')
    p.add_argument('file')
    p.add_argument('--old', nargs=2, required=True, metavar=('REGULAR', 'BOLD'))
    p.add_argument('--new', nargs=2, required=True, metavar=('REGULAR', 'BOLD'))
    p.add_argument('--min-delta', type=float, default=3.0)
    a = ap.parse_args()
    return cmd_apply(a) if a.cmd == 'apply' else cmd_measure(a)


if __name__ == '__main__':
    sys.exit(main() or 0)
