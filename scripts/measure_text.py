#!/usr/bin/env python3
"""Measure rendered text width with an Arial-metric font (Liberation Sans).

  python3 scripts/measure_text.py "α-Ketoglutarate" "Succinyl-CoA" --size 16
  python3 scripts/measure_text.py "Deep Learning Models" --size 32 --bold

Set FONT_REGULAR / FONT_BOLD to use other .ttf files (e.g. Arial on macOS:
/System/Library/Fonts/Supplemental/Arial.ttf and "Arial Bold.ttf").
"""
import argparse
import os

from PIL import ImageFont

CANDIDATES = {
    False: ['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            'C:/Windows/Fonts/arial.ttf'],
    True: ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
           '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
           'C:/Windows/Fonts/arialbd.ttf'],
}


def font_path(bold):
    env = os.environ.get('FONT_BOLD' if bold else 'FONT_REGULAR')
    for p in ([env] if env else []) + CANDIDATES[bold]:
        if p and os.path.exists(p):
            return p
    raise SystemExit('no Arial-metric font found; set FONT_REGULAR / FONT_BOLD')


def text_width(text, size, bold=False):
    return ImageFont.truetype(font_path(bold), size).getlength(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('texts', nargs='+')
    ap.add_argument('--size', type=float, default=16)
    ap.add_argument('--bold', action='store_true')
    a = ap.parse_args()
    for t in a.texts:
        print(f'{round(text_width(t, a.size, a.bold)):5d}  {t}')


if __name__ == '__main__':
    main()
