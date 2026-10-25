#!/usr/bin/env python3
"""Merge svgo-optimised pieces (made by svg_split.py --pieces) back into one SVG.

The head (incl. the mask) is taken from the first piece; every piece must carry the
same head. Pieces whose body svgo removed entirely (e.g. pieces holding only empty
paths) are skipped.

    python3 scripts/svg_merge.py merged.svg pieces/raw_part*.min.svg
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgtools import split_svg  # noqa: E402


def part_no(path):
    m = re.search(r'_part(\d+)', os.path.basename(path))
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('pieces', nargs='+')
    a = ap.parse_args()

    head = foot = None
    bodies = []
    for f in sorted(a.pieces, key=part_no):
        try:
            h, paths, ft = split_svg(open(f, encoding='utf-8').read())
        except ValueError:
            print('skip (no body):', f)
            continue
        if head is None:
            head, foot = h, ft
        elif h != head:
            sys.exit(f'head differs in {f}; were all pieces optimised with the same svgo config?')
        bodies.append(''.join(paths))
    if head is None:
        sys.exit('no piece had a body')
    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write(head + ''.join(bodies) + foot)
    print(a.out, os.path.getsize(a.out))


if __name__ == '__main__':
    main()
