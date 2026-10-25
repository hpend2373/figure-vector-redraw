#!/usr/bin/env python3
"""Cut a traced SVG into pieces that each keep the full head (incl. the <mask>).

Two uses:

1. Before svgo, for big files (svgo is superlinear; a 30 MB file can run for an hour,
   while 8 MB pieces take ~1-3 min each):

       python3 scripts/svg_split.py raw.svg pieces/raw --pieces 6
       for f in pieces/raw_part*.svg; do npx svgo@3.3.2 --config scripts/svgo.config.cjs -i "$f" -o "${f%.svg}.min.svg"; done
       python3 scripts/svg_merge.py merged.svg pieces/raw_part*.min.svg

2. After svgo, to meet an upload limit (e.g. 2 MB per asset; servers may inflate files
   10-15 %, so aim for 1.5 MB):

       python3 scripts/svg_split.py merged.svg chunks/art --max-bytes 1500000

   Stack the chunks in ONE element so they recombine exactly, e.g. in CSS
   (the first url is the top layer, i.e. the last chunk):

       .art { background-image: url(part3), url(part2), url(part1);
              background-size: 100% 100%; background-repeat: no-repeat; }
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgtools import split_svg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', help='input SVG')
    ap.add_argument('prefix', help='output prefix; files are <prefix>_part<N>.svg')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--pieces', type=int, help='split the body into this many pieces of similar size')
    g.add_argument('--max-bytes', type=int, help='largest allowed output file in bytes')
    a = ap.parse_args()

    text = open(a.src, encoding='utf-8').read()
    head, paths, foot = split_svg(text)
    if not paths:
        sys.exit('no body paths found')

    chunks, cur, size = [], [], 0
    if a.pieces:
        target = sum(map(len, paths)) / a.pieces
        for p in paths:
            if cur and size + len(p) > target and len(chunks) < a.pieces - 1:
                chunks.append(cur)
                cur, size = [], 0
            cur.append(p)
            size += len(p)
    else:
        budget = a.max_bytes - len(head.encode()) - len(foot.encode())
        if budget <= 0:
            sys.exit('the head (mask) alone exceeds --max-bytes; simplify the mask first')
        for p in paths:
            n = len(p.encode())
            if cur and size + n > budget:
                chunks.append(cur)
                cur, size = [], 0
            cur.append(p)
            size += n
    chunks.append(cur)

    os.makedirs(os.path.dirname(os.path.abspath(a.prefix)), exist_ok=True)
    for i, c in enumerate(chunks, 1):
        out = f'{a.prefix}_part{i}.svg'
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(head + ''.join(c) + foot)
        print(out, os.path.getsize(out))


if __name__ == '__main__':
    main()
