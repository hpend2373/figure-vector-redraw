#!/usr/bin/env python3
"""Turn a Design-canvas artboard (.dc.html) into a standalone HTML page for local review.

Takes the fragment between <x-dc> and </x-dc>, drops the <helmet> wrapper (its <style>
stays), swaps /_blob/<id> asset URLs for local files and fills {{holes}}.

  python3 scripts/build_preview.py Artboard.dc.html preview.html \
      --blob-map blobs.json --hole titleTerm="Activity Inference"
  node scripts/render.js page preview.html preview.png --scale 2

blobs.json maps asset ids to local paths, e.g.
  {"a373b3d3704f7fc97543fa01d4dd89ea": "assets/01_tca_cycle.svg"}
Relative paths are resolved against the JSON file's folder. <sc-if>/<sc-for> blocks are
left as-is (browsers render their children), so fill holes they depend on by hand.
"""
import argparse
import json
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('artboard')
    ap.add_argument('out')
    ap.add_argument('--blob-map', help='JSON {asset_id: local_path}')
    ap.add_argument('--hole', action='append', default=[], help='name=value')
    a = ap.parse_args()

    src = open(a.artboard, encoding='utf-8').read()
    i, j = src.find('<x-dc>'), src.rfind('</x-dc>')
    if i < 0 or j < 0:
        sys.exit('no <x-dc> fragment found')
    body = src[i + len('<x-dc>'):j].replace('<helmet>', '').replace('</helmet>', '')

    if a.blob_map:
        base = os.path.dirname(os.path.abspath(a.blob_map))
        mapping = json.load(open(a.blob_map, encoding='utf-8'))
        for k, v in mapping.items():
            p = v if os.path.isabs(v) else os.path.join(base, v)
            body = body.replace('/_blob/' + k, 'file://' + p)
    missing = sorted(set(re.findall(r'/_blob/([0-9a-f]{32})', body)))
    if missing:
        print('unmapped assets:', ', '.join(missing), file=sys.stderr)

    for h in a.hole:
        name, _, value = h.partition('=')
        body = re.sub(r'\{\{\s*' + re.escape(name) + r'\s*\}\}', value, body)
    left = sorted(set(re.findall(r'\{\{\s*([^}]+?)\s*\}\}', body)))
    if left:
        print('unfilled holes:', ', '.join(left), file=sys.stderr)

    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write('<!doctype html><html><head><meta charset="utf-8"></head>'
                 '<body style="margin:0">' + body + '</body></html>')
    print(a.out)


if __name__ == '__main__':
    main()
