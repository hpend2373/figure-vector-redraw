"""Shared helpers for traced (vectorizer-style) SVG files.

A traced file looks like:

    <svg ...><defs><mask id="..."> ...alpha paths... </mask></defs>
    <g id="..." mask="url(#...)"><g transform="scale(0.5)"> ...colour paths... </g></g></svg>

After svgo the inner scale group is usually folded away:

    <svg ...><defs><mask ...>...</mask></defs><g id="..." mask="url(#...)"> ...paths... </g></svg>

`split_svg` returns (head, body_paths, foot) so a file can be cut into pieces that each
keep the full head (including the mask) and therefore render identically when stacked.
"""
import re

_BODY_OPEN = re.compile(r'<g\b[^>]*\bmask="url\(#[^)]*\)"[^>]*>(?:\s*<g\b[^>]*>)?')
_PATH = re.compile(r'<path\b[^>]*/>\s*')


def split_svg(text):
    """Split a traced SVG into (head, [path elements], foot).

    head ends right after the masked body group (and its inner transform group, if any);
    foot starts after the last body path. Raises ValueError when the body holds anything
    other than <path/> elements, because those would be dropped silently otherwise.
    """
    m = _BODY_OPEN.search(text)
    if not m:
        raise ValueError('no <g mask="url(#...)"> body group found')
    rest = text[m.end():]
    paths = [p.group(0) for p in _PATH.finditer(rest)]
    if not paths:
        return text[:m.end()], [], rest
    last = None
    for last in _PATH.finditer(rest):
        pass
    body = rest[:last.end()]
    if ''.join(paths) != body:
        raise ValueError('body contains elements other than <path/>; refusing to split')
    return text[:m.end()], paths, rest[last.end():]


_NUM = re.compile(r'-?\d+(?:\.\d+)?')
_TRANSLATE = re.compile(r'translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)')


def raw_path_bbox(tag):
    """Bounding box of a *raw* traced path (absolute M/C/L/Z commands + translate()).

    Returns (x0, y0, x1, y1) in the path's own coordinate space, or None for empty paths.
    Do not use on svgo output: svgo rewrites paths with relative commands.
    """
    dm = re.search(r'\sd="([^"]*)"', tag)
    if not dm or not dm.group(1).strip():
        return None
    tm = _TRANSLATE.search(tag)
    tx, ty = (float(tm.group(1)), float(tm.group(2))) if tm else (0.0, 0.0)
    v = [float(x) for x in _NUM.findall(dm.group(1))]
    xs = [tx + v[i] for i in range(0, len(v) - 1, 2)]
    ys = [ty + v[i] for i in range(1, len(v), 2)]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def fill_luminance(tag):
    m = re.search(r'fill="#([0-9A-Fa-f]{6})"', tag)
    if not m:
        return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b
