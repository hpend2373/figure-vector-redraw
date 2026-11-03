"""Turn a Design .dc.html artboard into a standalone preview HTML (blob ids -> local files) and render PNGs.

  python3 dc_preview.py board.dc.html blobs.json out.png [--scale 1] [--term "activity inference"] [--crop x,y,w,h]
"""
import argparse, json, os, re, sys
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('blobs'); ap.add_argument('out')
ap.add_argument('--scale', type=float, default=1); ap.add_argument('--term', default=None)
ap.add_argument('--crop', default=None)
a = ap.parse_args()
m = json.load(open(a.blobs))
s = open(a.src, encoding='utf-8').read()
missing = sorted({i for i in re.findall(r'/_blob/([0-9a-f]{32})', s) if i not in m})
if missing:
    sys.exit('missing blobs: ' + ', '.join(missing))
s = re.sub(r'/_blob/([0-9a-f]{32})', lambda g: 'file://' + os.path.abspath(m[g.group(1)]), s)
s = s.replace('<script src="./support.js"></script>', '')
s = re.sub(r'<script type="text/x-dc".*?</script>', '', s, flags=re.S)
s = s.replace('<x-dc>', '').replace('</x-dc>', '').replace('<helmet>', '').replace('</helmet>', '')
if a.term is None:
    t = re.search(r"isFlux \? '([^']*)' : '([^']*)'", open(a.src, encoding='utf-8').read())
    a.term = t.group(2) if t else ''
s = s.replace('{{titleTerm}}', a.term)
html = os.path.splitext(a.out)[0] + '.html'
open(html, 'w', encoding='utf-8').write(s)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=a.scale)
    pg.goto('file://' + os.path.abspath(html)); pg.wait_for_timeout(800)
    kw = {}
    if a.crop:
        x, y, w, h = map(float, a.crop.split(',')); kw['clip'] = {'x': x, 'y': y, 'width': w, 'height': h}
    pg.screenshot(path=a.out, **kw); b.close()
print('wrote', a.out)
