#!/usr/bin/env python3
"""Style inventory for a figure: SVG, or an HTML / Claude Design artboard (.dc.html).

Counts what the eye reads as a "visual language" (palette, shading, texture, strokes, shapes,
type, decoration) and flags combinations worth reviewing. It does NOT judge whether AI made
the figure; flags are prompts for a human look, not verdicts.

  python3 style_audit.py figure.svg [--md report.md] [--json report.json]
  python3 style_audit.py Artboard.dc.html
"""
import argparse
import colorsys
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

NAMED = {'white': '#ffffff', 'black': '#000000', 'red': '#ff0000', 'blue': '#0000ff', 'green': '#008000',
         'gray': '#808080', 'grey': '#808080', 'orange': '#ffa500', 'yellow': '#ffff00', 'none': None,
         'transparent': None, 'currentcolor': None}


def norm_color(v):
    """CSS colour -> ('#rrggbb', alpha) or None."""
    if not v:
        return None
    v = v.strip().lower()
    if v.startswith('url('):
        return None
    if v in NAMED:
        return (NAMED[v], 1.0) if NAMED[v] else None
    m = re.fullmatch(r'#([0-9a-f]{3})', v)
    if m:
        return ('#' + ''.join(c * 2 for c in m.group(1)), 1.0)
    m = re.fullmatch(r'#([0-9a-f]{6})([0-9a-f]{2})?', v)
    if m:
        return ('#' + m.group(1), int(m.group(2), 16) / 255 if m.group(2) else 1.0)
    m = re.fullmatch(r'rgba?\(([^)]+)\)', v)
    if m:
        parts = [p.strip() for p in re.split(r'[,\s/]+', m.group(1)) if p.strip()]
        try:
            rgb = [float(p[:-1]) * 2.55 if p.endswith('%') else float(p) for p in parts[:3]]
            a = float(parts[3][:-1]) / 100 if len(parts) > 3 and parts[3].endswith('%') else (float(parts[3]) if len(parts) > 3 else 1.0)
            return ('#%02x%02x%02x' % tuple(max(0, min(255, round(c))) for c in rgb), a)
        except ValueError:
            return None
    return None


def hls(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, l, s


def chroma(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b)


def is_neutral(hexc):
    return chroma(hexc) < 0.08


def is_warm(hexc):
    h, l, s = hls(hexc)
    return not is_neutral(hexc) and (h < 70 or h > 330)


def parse_style(s):
    d = {}
    for part in (s or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            d[k.strip().lower()] = v.strip()
    return d


def num(v, default=None):
    m = re.match(r'\s*(-?[\d.]+)', v or '')
    return float(m.group(1)) if m else default


class Inventory:
    def __init__(self):
        self.fill = Counter(); self.stroke = Counter(); self.bg = []
        self.grad = Counter(); self.grad_uses = 0; self.filters = Counter(); self.filter_uses = 0
        self.patterns = 0; self.shadows = 0; self.translucent = 0
        self.stroke_w = Counter(); self.caps = Counter(); self.radii = Counter()
        self.font_size = Counter(); self.font_weight = Counter(); self.font_family = Counter(); self.texts = 0
        self.rasters = 0; self.decor = Counter(); self.elements = 0
        self.art_elements = 0; self.art_blocks = []; self.include_art = False; self.skip = None; self.root_family = None

    # ---------- SVG ----------
    def _walk(self, el, in_art, top=False):
        tag = el.tag.split('}')[-1]
        ident = ' '.join(filter(None, [el.get('id'), el.get('data-name'), el.get('class')]))
        if not top and not in_art and not self.include_art:
            if tag == 'svg' or (self.skip and ident and re.search(self.skip, ident)):
                self.art_blocks.append(ident or tag)
                in_art = True
        yield el, in_art
        for c in el:
            yield from self._walk(c, in_art)

    def svg(self, root, vb=None):
        css = {}
        for st in root.iter():
            if st.tag.split('}')[-1] == 'style' and st.text:
                for sel, body in re.findall(r'\.([\w-]+)\s*\{([^}]*)\}', st.text):
                    css[sel] = parse_style(body)
        if vb is None:
            v = root.get('viewBox')
            vb = [float(x) for x in re.split(r'[\s,]+', v.strip())] if v else [0, 0, num(root.get('width'), 0), num(root.get('height'), 0)]
        shadow_ids = set()
        for f in root.iter():
            if f.tag.split('}')[-1] == 'filter' and f.get('id'):
                prims = {c.tag.split('}')[-1] for c in f.iter()}
                if 'feDropShadow' in prims or {'feGaussianBlur', 'feOffset'} <= prims:
                    shadow_ids.add(f.get('id'))
        for el, in_art in self._walk(root, False, top=True):
            tag = el.tag.split('}')[-1]
            if in_art:
                self.art_elements += 1
                continue
            self.elements += 1
            st = {}
            for c in (el.get('class') or '').split():
                st.update(css.get(c, {}))
            for k in ('fill', 'stroke', 'stroke-width', 'stroke-linecap', 'opacity', 'fill-opacity', 'font-size',
                      'font-weight', 'font-family', 'filter', 'rx'):
                if el.get(k) is not None:
                    st[k] = el.get(k)
            st.update(parse_style(el.get('style')))
            if tag in ('linearGradient', 'radialGradient'):
                self.grad[tag] += 1
            elif tag == 'pattern':
                self.patterns += 1
            elif tag.startswith('fe'):
                self.filters[tag] += 1
            elif tag == 'image':
                href = el.get('href') or el.get('{http://www.w3.org/1999/xlink}href') or ''
                if not href.startswith('data:image/svg'):
                    self.rasters += 1
            ident = ' '.join(filter(None, [el.get('id'), el.get('class'), el.get('data-name'),
                                           el.get('{http://www.inkscape.org/namespaces/inkscape}label')])).lower()
            for kw in ('background', 'bg', 'decor', 'circuit', 'pcb', 'ornament', 'badge', 'ribbon', 'texture', 'noise', 'glow', 'sparkle'):
                if re.search(r'(^|[^a-z])' + kw + r'([^a-z]|$)', ident):
                    self.decor[kw] += 1
            if tag in ('defs', 'linearGradient', 'radialGradient', 'stop', 'filter', 'clipPath', 'mask', 'pattern', 'style', 'title', 'desc', 'metadata'):
                continue
            if tag.startswith('fe'):
                continue
            fill, stroke = st.get('fill'), st.get('stroke')
            for v, cnt in ((fill, self.fill), (stroke, self.stroke)):
                if v and v.startswith('url('):
                    self.grad_uses += 1
                c = norm_color(v)
                if c:
                    cnt[c[0]] += 1
            if st.get('filter', 'none') not in ('none', ''):
                self.filter_uses += 1
                fm = re.search(r'url\(#([^)]+)\)', st['filter'])
                if fm and fm.group(1) in shadow_ids:
                    self.shadows += 1
            op = min(num(st.get('opacity'), 1), num(st.get('fill-opacity'), 1))
            if op < 0.999:
                self.translucent += 1
            if stroke and stroke != 'none' and tag in ('path', 'line', 'polyline', 'polygon', 'rect', 'circle', 'ellipse'):
                self.stroke_w[round(num(st.get('stroke-width'), 1) * 2) / 2] += 1
                self.caps[st.get('stroke-linecap', 'butt')] += 1
            if tag == 'rect':
                w, h = num(el.get('width'), 0), num(el.get('height'), 0)
                rx = num(st.get('rx') or el.get('ry'), 0)
                if w * h > 0 and rx > 0 and min(w, h) > 24:
                    self.radii[round(rx)] += 1
                if vb and w >= 0.95 * vb[2] and h >= 0.95 * vb[3]:
                    c = norm_color(fill)
                    if c:
                        self.bg.append(c[0])
            if tag == 'text':
                self.texts += 1
                self._font(st)
            if tag == 'tspan' and st.get('font-size') and not (el.get('dy') or el.get('baseline-shift')):
                self.font_size[round(num(st['font-size'], 0))] += 1

    def _font(self, st):
        if st.get('font-size'):
            self.font_size[round(num(st['font-size'], 0))] += 1
        w = st.get('font-weight', '400')
        w = {'normal': '400', 'bold': '700'}.get(w, w)
        self.font_weight[w] += 1
        fam = (st.get('font-family') or 'inherit').split(',')[0].strip().strip('\'"')
        self.font_family[fam] += 1

    # ---------- HTML / Design artboard ----------
    def html(self, text):
        rf = re.search(r'font-family:\s*([^;"]+)', text)
        self.root_family = rf.group(1).split(',')[0].strip().strip('\'"') if rf else None
        for m in re.finditer(r'<svg\b.*?</svg>', text, flags=re.S):
            try:
                self.svg(ET.fromstring(m.group(0)))
            except ET.ParseError:
                pass
        rest = re.sub(r'<svg\b.*?</svg>', '', text, flags=re.S)
        for m in re.finditer(r'<(div|span|p|h\d|img)\b([^>]*)>([^<]*)', rest):
            tag, attrs, inner = m.groups()
            sm = re.search(r'style="([^"]*)"', attrs)
            st = parse_style(sm.group(1)) if sm else {}
            self.elements += 1
            bgc = norm_color(st.get('background') or st.get('background-color'))
            if bgc:
                self.fill[bgc[0]] += 1
                if bgc[1] < 0.999:
                    self.translucent += 1
                if num(st.get('width'), 0) >= 1800 and num(st.get('height'), 0) >= 1000:
                    self.bg.append(bgc[0])
            if 'gradient(' in (st.get('background') or '') + (st.get('background-image') or ''):
                self.grad['css-gradient'] += 1; self.grad_uses += 1
            if st.get('box-shadow', 'none') != 'none' and 'box-shadow' in st:
                self.shadows += 1
            if st.get('filter') or st.get('backdrop-filter'):
                self.filter_uses += 1
            if st.get('border-radius'):
                r = num(st['border-radius'], 0)
                if r > 0:
                    self.radii[round(r)] += 1
            if st.get('border') and 'none' not in st['border']:
                bw = num(st['border'], 0)
                self.stroke_w[round(bw * 2) / 2] += 1
                c = norm_color(st['border'].split()[-1])
                if c:
                    self.stroke[c[0]] += 1
            if inner.strip() or st.get('font-size'):
                if inner.strip():
                    self.texts += 1
                    self._font(st)
            if st.get('color'):
                c = norm_color(st['color'])
                if c:
                    self.fill[c[0]] += 1
            if tag == 'img' and re.search(r'\.(png|jpe?g|webp)', attrs):
                self.rasters += 1
        if 'inherit' in self.font_family and self.root_family:
            self.font_family[self.root_family] += self.font_family.pop('inherit')


def report(inv):
    colours = inv.fill + inv.stroke
    chrom = {c: n for c, n in colours.items() if not is_neutral(c)}
    tot_ch = sum(chrom.values()) or 1
    hues = Counter(int(hls(c)[0] // 30) for c, n in chrom.items() if n / tot_ch >= 0.02)
    warm = sum(n for c, n in chrom.items() if is_warm(c)); total_c = sum(chrom.values()) or 1
    bg = Counter(inv.bg).most_common(1)[0][0] if inv.bg else None
    sizes = sorted(inv.font_size)
    bold = sum(n for w, n in inv.font_weight.items() if num(w, 400) >= 600)
    tw = sum(inv.font_weight.values()) or 1
    flags = []
    def flag(axis, cond, msg):
        if cond:
            flags.append((axis, msg))
    flag('팔레트', bg is not None and (chroma(bg) >= 0.015 or hls(bg)[1] < 0.93), f'배경이 흰색이 아닌 색조·회색을 띰({bg}). 흰 바탕 대안과 비교 검토')
    flag('팔레트', len(hues) > 6, f'유채색 색상군이 {len(hues)}개(30° 단위). 역할별 색 수를 줄일지 검토')
    flag('팔레트', total_c > 20 and warm / total_c > 0.6, f'유채색 사용의 {warm / total_c:.0%}가 따뜻한 계열. 전체 색조 막이 씌워졌는지 검토')
    flag('음영·재질', inv.shadows >= 3, f'그림자 {inv.shadows}곳. 같은 부드러운 그림자가 성격이 다른 요소에 반복되는지 검토')
    flag('음영·재질', inv.shadows and inv.grad_uses >= 5, f'그림자와 그라데이션({inv.grad_uses}곳)이 함께 쓰임. 표현 방식 혼용 여부 검토')
    flag('음영·재질', inv.filters.get('feGaussianBlur', 0) >= 3, f'흐림 필터 {inv.filters["feGaussianBlur"]}개. 광택·글로·안개 효과인지 검토')
    flag('텍스처', inv.filters.get('feTurbulence', 0) or inv.patterns, f'노이즈(feTurbulence {inv.filters.get("feTurbulence", 0)})·패턴({inv.patterns}) 사용. 목적 있는 질감인지 검토')
    flag('외곽선', len(inv.stroke_w) > 6, f'선 두께가 {len(inv.stroke_w)}종. 역할별(패널·데이터·화살표) 두께 체계로 묶을지 검토')
    flag('도형·장식', len(inv.radii) > 3, f'모서리 반경 {len(inv.radii)}종 {sorted(inv.radii)}. 패널 모양 문법 통일 검토')
    flag('도형·장식', sum(inv.decor.values()) > 0, f'장식으로 보이는 이름의 요소: {dict(inv.decor)}. 데이터인지 장식인지 확인')
    flag('타이포그래피', len(sizes) > 7, f'글자 크기 {len(sizes)}종 {sizes}. 3–5단계로 정리 검토')
    flag('타이포그래피', inv.texts >= 6 and bold / tw > 0.5, f'텍스트의 {bold / tw:.0%}가 굵음. 모든 구역이 같은 무게로 경쟁하는지 검토')
    flag('타이포그래피', len(inv.font_family) > 2, f'글꼴 {len(inv.font_family)}종 {list(inv.font_family)}. 혼용 의도 확인')
    flag('레이아웃', inv.rasters, f'래스터 이미지 {inv.rasters}개 포함. 벡터 그림 안에서 해상도·재질이 섞이는지 확인')
    metrics = {
        'background': bg, 'colours_total': len(colours), 'chromatic_colours': len(chrom), 'hue_groups': len(hues),
        'warm_share': round(warm / total_c, 2), 'top_colours': colours.most_common(10),
        'gradients': dict(inv.grad), 'gradient_uses': inv.grad_uses, 'filters': dict(inv.filters), 'filter_uses': inv.filter_uses,
        'shadows': inv.shadows, 'translucent_elements': inv.translucent, 'patterns': inv.patterns,
        'stroke_widths': dict(sorted(inv.stroke_w.items())), 'linecaps': dict(inv.caps), 'corner_radii': dict(sorted(inv.radii.items())),
        'texts': inv.texts, 'font_sizes': dict(sorted(inv.font_size.items())), 'font_weights': dict(inv.font_weight),
        'font_families': dict(inv.font_family), 'rasters': inv.rasters, 'decor_names': dict(inv.decor), 'elements': inv.elements,
        'art_blocks': len(inv.art_blocks), 'art_elements': inv.art_elements}
    return metrics, flags


def to_md(path, metrics, flags):
    m = metrics
    rows = [
        ('팔레트', f"배경 {m['background']}, 유채색 {m['chromatic_colours']}종 / 색상군 {m['hue_groups']}개, 따뜻한 계열 비율 {m['warm_share']:.0%}"),
        ('음영·재질', f"그림자 {m['shadows']}, 그라데이션 {sum(m['gradients'].values())}개(사용 {m['gradient_uses']}곳), 필터 사용 {m['filter_uses']}곳, 반투명 {m['translucent_elements']}"),
        ('텍스처', f"패턴 {m['patterns']}, 노이즈 {m['filters'].get('feTurbulence', 0)}"),
        ('외곽선', f"선 두께 {len(m['stroke_widths'])}종 {list(m['stroke_widths'])}, 끝모양 {m['linecaps']}"),
        ('도형·장식', f"모서리 반경 {m['corner_radii']}, 장식 이름 {m['decor_names'] or '없음'}"),
        ('타이포그래피', f"텍스트 {m['texts']}개, 크기 {list(m['font_sizes'])}, 굵기 {m['font_weights']}, 글꼴 {list(m['font_families'])}"),
        ('레이아웃', f"요소 {m['elements']}개, 래스터 {m['rasters']}개 (구역 비중·정렬은 화면으로 확인)"),
        ('제외한 그림 블록', f"{m['art_blocks']}개 블록·{m['art_elements']}개 요소 (중첩 svg 또는 --skip 일치; 데이터·도식 본체는 따로 판단)"),
    ]
    out = [f'# 스타일 점검: {path}', '', '| 축 | 집계 |', '|---|---|'] + [f'| {a} | {b} |' for a, b in rows]
    out += ['', '## 검토 권장 항목', '']
    out += [f'- **{a}** — {b}' for a, b in flags] or ['- 자동 집계로 걸린 항목 없음 (화면 검토는 별도로 필요)']
    out += ['', '> 이 집계는 시각 언어의 일관성을 보기 위한 것이며, 제작 주체(AI/사람)를 판별하지 않습니다.',
            '> 상위 색: ' + ', '.join(f'{c}×{n}' for c, n in m['top_colours'])]
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--md'); ap.add_argument('--json')
    ap.add_argument('--skip', help='regex on id/data-name/class of groups that hold data or diagram art (excluded from style stats)')
    ap.add_argument('--include-art', action='store_true', help='count nested <svg> art blocks too')
    a = ap.parse_args()
    text = open(a.file, encoding='utf-8').read()
    inv = Inventory(); inv.skip = a.skip; inv.include_art = a.include_art
    if a.file.lower().endswith('.svg'):
        inv.svg(ET.fromstring(text.encode('utf-8')))
    else:
        inv.html(text)
    metrics, flags = report(inv)
    md = to_md(a.file, metrics, flags)
    if a.md:
        open(a.md, 'w', encoding='utf-8').write(md)
    if a.json:
        json.dump({'metrics': metrics, 'flags': flags}, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(md)


if __name__ == '__main__':
    sys.exit(main())
