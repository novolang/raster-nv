#!/usr/bin/env python3
# compare.py - run the scenarios through raster-nv's probe and through the
# oracle, and report how far apart the coverage planes are.
#
# usage: compare.py PROBE_BINARY [MODE]
#
# MODE is `fill` (FreeType) for now; each mode prints one line per scenario
# with the largest and the mean difference in coverage levels, and the exit
# status is nonzero when a scenario is past its bound.
import math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cairo
import exact
import freetype
import ftglyph

K = 0.5522847498  # four cubics make a circle


def circle(cx, cy, r):
    k = K * r
    return [('M', cx + r, cy), ('C', cx + r, cy + k, cx + k, cy + r, cx, cy + r),
            ('C', cx - k, cy + r, cx - r, cy + k, cx - r, cy),
            ('C', cx - r, cy - k, cx - k, cy - r, cx, cy - r),
            ('C', cx + k, cy - r, cx + r, cy - k, cx + r, cy), ('Z',)]


def poly(pts, closed=True):
    out = [('M',) + pts[0]] + [('L',) + p for p in pts[1:]]
    return out + ([('Z',)] if closed else [])


def star(cx, cy, r, order=2):
    pts = []
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi * order / 5
        pts.append((round(cx + r * math.cos(a), 4), round(cy + r * math.sin(a), 4)))
    return poly(pts)


# Curved scenarios are checked against exact.py: FreeType flattens a curve
# more coarsely than the answer being tested.
EXACT = {'circle-fine', 'quad-blob', 'ring-opposite', 'circle-default'}

# name, width, height, rule, tolerance, commands, bound (largest allowed difference)
FILL = [
    ('half-diagonal', 8, 8, 'nz', 0.25, poly([(0, 0), (8, 0), (0, 8)]), 1),
    ('fractional-rect', 8, 8, 'nz', 0.25, poly([(1.5, 1.5), (6.5, 1.5), (6.5, 5.25), (1.5, 5.25)]), 1),
    ('triangle', 24, 24, 'nz', 0.25, poly([(2.25, 3.5), (20.75, 7.125), (9.5, 21.875)]), 2),
    ('thin-sliver', 24, 24, 'nz', 0.25, poly([(1, 1), (22.5, 12.25), (1, 2.25)]), 2),
    ('shallow-edge', 24, 8, 'nz', 0.25, poly([(0, 6), (24, 2.5), (24, 8), (0, 8)]), 2),
    ('steep-edge', 8, 24, 'nz', 0.25, poly([(2.5, 0), (5.25, 24), (0, 24), (0, 0)]), 2),
    ('circle-fine', 24, 24, 'nz', 0.01, circle(12, 12, 9.5), 2),
    ('circle-default', 24, 24, 'nz', 0.25, circle(12, 12, 9.5), 64),
    ('quad-blob', 24, 24, 'nz', 0.01, [('M', 3, 20), ('Q', 12, -4, 21, 20), ('Z',)], 2),
    ('star-nonzero', 32, 32, 'nz', 0.25, star(16, 16, 14), 2),
    ('star-evenodd', 32, 32, 'eo', 0.25, star(16, 16, 14), 2),
    ('ring-opposite', 24, 24, 'nz', 0.01,
     circle(12, 12, 10) + [('M', 12 + 5, 12), ('C', 12 + 5, 12 - 2.7614, 12 + 2.7614, 12 - 5, 12, 12 - 5),
                           ('C', 12 - 2.7614, 12 - 5, 12 - 5, 12 - 2.7614, 12 - 5, 12),
                           ('C', 12 - 5, 12 + 2.7614, 12 - 2.7614, 12 + 5, 12, 12 + 5),
                           ('C', 12 + 2.7614, 12 + 5, 12 + 5, 12 + 2.7614, 12 + 5, 12), ('Z',)], 2),
    ('ring-same-nonzero', 24, 24, 'nz', 0.25,
     poly([(2, 2), (22, 2), (22, 22), (2, 22)]) + poly([(6, 6), (18, 6), (18, 18), (6, 18)]), 1),
    ('ring-same-evenodd', 24, 24, 'eo', 0.25,
     poly([(2, 2), (22, 2), (22, 22), (2, 22)]) + poly([(6, 6), (18, 6), (18, 18), (6, 18)]), 1),
    ('clipped-left', 12, 12, 'nz', 0.25, poly([(-6.5, 2.25), (7.5, 3), (4.25, 14), (-3, 10)]), 2),
    ('clipped-right', 12, 12, 'nz', 0.25, poly([(6.5, -3.25), (20, 3), (14.25, 9), (4, 15.5)]), 2),
    ('clipped-both', 12, 12, 'nz', 0.25, poly([(-5, 2.5), (17, 4.25), (17, 9.75), (-5, 8)]), 2),
    ('off-screen', 12, 12, 'nz', 0.25, poly([(30, 30), (40, 30), (40, 40)]), 0),
    ('open-subpath-closes', 16, 16, 'nz', 0.25, poly([(2, 2), (14, 3), (8, 14)], closed=False), 2),
]


def scenario_lines(table):
    lines = []
    for (name, w, h, rule, tol, cmds, _bound) in table:
        lines.append('%s %d %d %s %s %s' % ((name, w, h, rule, tol, path_tokens(cmds))))
    return '\n'.join(lines) + '\n'


def path_tokens(cmds):
    toks = []
    for c in cmds:
        toks.append(c[0])
        toks.extend(repr(float(v)) for v in c[1:])
    return ' '.join(toks)


def parse(output):
    got = {}
    name = None
    for line in output.splitlines():
        if line.startswith('== '):
            name = line[3:]
            got[name] = []
        elif name is not None:
            got[name].append(line.split())
    return got


def run_probe(probe, mode, text):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        f.write(text)
        path = f.name
    out = subprocess.run([probe, mode, path], capture_output=True, text=True).stdout
    os.unlink(path)
    return out


def check_fill(probe):
    failures = 0
    got = parse(run_probe(probe, 'fill', scenario_lines(FILL)))
    for (name, w, h, rule, tol, cmds, bound) in FILL:
        if name in EXACT:
            want = exact.render(cmds, w, h, even_odd=(rule == 'eo'))
        else:
            want = freetype.render(cmds, w, h, even_odd=(rule == 'eo'))
        failures += report(name, got.get(name, []), want, w, h, bound)
    print('fill: %d scenarios, %d past their bound' % (len(FILL), failures))
    return failures


def report(name, rows, want, w, h, bound, mean_bound=None):
    if len(rows) != h:
        print('FAIL %-26s the probe answered %d rows' % (name, len(rows)))
        return 1
    diffs = [abs(int(rows[y][x]) - want[y][x]) for y in range(h) for x in range(w)]
    worst, mean = max(diffs), sum(diffs) / len(diffs)
    ok = worst <= bound and (mean_bound is None or mean <= mean_bound)
    print('%s %-26s largest %3d (bound %d)  mean %.3f' % ('ok  ' if ok else 'FAIL', name, worst, bound, mean))
    return 0 if ok else 1


# ---- cairo: strokes ----

CAPS = {'b': cairo.LINE_CAP_BUTT, 'r': cairo.LINE_CAP_ROUND, 's': cairo.LINE_CAP_SQUARE}
JOINS = {'m': cairo.LINE_JOIN_MITER, 'r': cairo.LINE_JOIN_ROUND, 'b': cairo.LINE_JOIN_BEVEL}


def trace(ctx, cmds):
    pen = (0.0, 0.0)
    for c in cmds:
        k = c[0]
        if k == 'M':
            ctx.move_to(c[1], c[2])
            pen = (c[1], c[2])
        elif k == 'L':
            ctx.line_to(c[1], c[2])
            pen = (c[1], c[2])
        elif k == 'Q':
            x0, y0 = pen
            ctx.curve_to(x0 + 2 / 3 * (c[1] - x0), y0 + 2 / 3 * (c[2] - y0),
                         c[3] + 2 / 3 * (c[1] - c[3]), c[4] + 2 / 3 * (c[2] - c[4]), c[3], c[4])
            pen = (c[3], c[4])
        elif k == 'C':
            ctx.curve_to(*c[1:])
            pen = (c[5], c[6])
        else:
            ctx.close_path()


def cairo_a8(w, h, draw):
    surf = cairo.ImageSurface(cairo.FORMAT_A8, w, h)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_GRAY)
    ctx.set_tolerance(0.01)
    draw(ctx)
    surf.flush()
    data = surf.get_data()
    stride = surf.get_stride()
    return [[data[y * stride + x] for x in range(w)] for y in range(h)]


# name, W, H, width, cap, join, miter limit, dash offset, dashes, commands, largest bound, mean bound
#
# Cairo's scan converter quantises coverage to fifteen sub-scanlines
# vertically, so an edge that is not vertical is off by up to 17 levels from
# the exact area; the largest bound allows that, and the mean bound is what
# says the shapes agree.  A zero-length line with a square cap is left out:
# SVG and this package draw a square there, and cairo draws nothing.
STROKE = [
    ('line-butt', 32, 16, 4.0, 'b', 'm', 4.0, 0.0, [], poly([(3.5, 8), (28.25, 8)], False), 20, 1.0),
    ('line-round', 32, 16, 5.0, 'r', 'm', 4.0, 0.0, [], poly([(6, 8), (26, 8)], False), 20, 1.0),
    ('line-square', 32, 16, 5.0, 's', 'm', 4.0, 0.0, [], poly([(6, 8), (26, 8)], False), 20, 1.0),
    ('slanted-butt', 32, 32, 3.5, 'b', 'm', 4.0, 0.0, [], poly([(4, 5), (27, 26)], False), 20, 1.0),
    ('join-miter-right', 32, 32, 4.0, 'b', 'm', 4.0, 0.0, [], poly([(5, 26), (5, 8), (24, 8)], False), 20, 1.0),
    ('join-bevel-right', 32, 32, 4.0, 'b', 'b', 4.0, 0.0, [], poly([(5, 26), (5, 8), (24, 8)], False), 20, 1.0),
    ('join-round-right', 32, 32, 6.0, 'b', 'r', 4.0, 0.0, [], poly([(6, 27), (6, 9), (25, 9)], False), 20, 1.0),
    ('join-miter-acute', 40, 32, 3.0, 'b', 'm', 10.0, 0.0, [], poly([(3, 26), (34, 15), (3, 6)], False), 20, 1.0),
    ('join-miter-limited', 40, 32, 3.0, 'b', 'm', 2.0, 0.0, [], poly([(3, 26), (34, 15), (3, 6)], False), 20, 1.0),
    ('join-obtuse-miter', 40, 24, 4.0, 'b', 'm', 4.0, 0.0, [], poly([(3, 18), (20, 8), (37, 18)], False), 20, 1.0),
    ('closed-square-miter', 32, 32, 3.0, 'b', 'm', 4.0, 0.0, [], poly([(6, 6), (25, 6), (25, 25), (6, 25)]), 20, 1.0),
    ('closed-triangle-round', 32, 32, 3.0, 'b', 'r', 4.0, 0.0, [], poly([(6, 25), (16, 5), (26, 25)]), 20, 1.0),
    ('dashed-butt', 40, 12, 3.0, 'b', 'm', 4.0, 0.0, [5.0, 3.0], poly([(2, 6), (38, 6)], False), 20, 1.0),
    ('dashed-offset', 40, 12, 3.0, 'b', 'm', 4.0, 2.0, [5.0, 3.0], poly([(2, 6), (38, 6)], False), 20, 1.0),
    ('dashed-round-caps', 40, 12, 3.0, 'r', 'm', 4.0, 0.0, [4.0, 5.0], poly([(4, 6), (36, 6)], False), 20, 1.0),
    ('dashed-odd-pattern', 40, 12, 2.0, 'b', 'm', 4.0, 0.0, [6.0, 2.0, 1.0], poly([(2, 6), (38, 6)], False), 20, 1.0),
    ('curve-cubic', 40, 32, 3.0, 'b', 'r', 4.0, 0.0, [],
     [('M', 4, 26), ('C', 10, -6, 28, 40, 36, 6)], 24, 1.0),
    ('dot-round', 12, 12, 6.0, 'r', 'm', 4.0, 0.0, [], [('M', 6, 6), ('L', 6, 6)], 20, 1.0),
    ('dot-butt', 12, 12, 6.0, 'b', 'm', 4.0, 0.0, [], [('M', 6, 6), ('L', 6, 6)], 0, 0.0),
]


def check_stroke(probe):
    lines = []
    for (name, w, h, width, cap, join, miter, off, dashes, cmds, _b, _m) in STROKE:
        lines.append('%s %d %d %s %s %s %s %s %s %s' % (name, w, h, width, cap, join, miter, off,
                                                    ','.join(str(d) for d in dashes) or '-',
                                                    path_tokens(cmds)))
    got = parse(run_probe(probe, 'stroke', '\n'.join(lines) + '\n'))
    failures = 0
    for (name, w, h, width, cap, join, miter, off, dashes, cmds, bound, mean_bound) in STROKE:
        def draw(ctx, width=width, cap=cap, join=join, miter=miter, off=off, dashes=dashes, cmds=cmds):
            ctx.set_line_width(width)
            ctx.set_line_cap(CAPS[cap])
            ctx.set_line_join(JOINS[join])
            ctx.set_miter_limit(miter)
            if dashes:
                ctx.set_dash(dashes, off)
            trace(ctx, cmds)
            ctx.set_source_rgba(0, 0, 0, 1)
            ctx.stroke()
        failures += report(name, got.get(name, []), cairo_a8(w, h, draw), w, h, bound, mean_bound)
    print('stroke: %d scenarios, %d past their bound' % (len(STROKE), failures))
    return failures


# ---- cairo: gradients ----

EXTEND = {'pad': cairo.EXTEND_PAD, 'repeat': cairo.EXTEND_REPEAT, 'reflect': cairo.EXTEND_REFLECT}

# name, W, H, kind, spread, geometry (4 numbers), stops [(at, 'RRGGBB')], bound
PAINT = [
    ('linear-two-stops', 32, 8, 'linear', 'pad', (4, 0, 28, 0), [(0.0, 'ff0000'), (1.0, '0000ff')], 2),
    ('linear-three-stops', 32, 8, 'linear', 'pad', (0, 0, 32, 0), [(0.0, 'ff0000'), (0.3, '00ff00'), (1.0, '0000ff')], 2),
    ('linear-diagonal', 24, 24, 'linear', 'pad', (2, 3, 20, 18), [(0.0, 'ffff00'), (1.0, '102030')], 2),
    ('linear-repeat', 40, 4, 'linear', 'repeat', (5, 0, 15, 0), [(0.0, '000000'), (1.0, 'ffffff')], 2),
    ('linear-reflect', 40, 4, 'linear', 'reflect', (5, 0, 15, 0), [(0.0, '000000'), (1.0, 'ffffff')], 2),
    ('linear-hard-stop', 32, 4, 'linear', 'pad', (0, 0, 32, 0), [(0.0, 'ff0000'), (0.5, 'ff0000'), (0.5, '0000ff'), (1.0, '0000ff')], 130),
    ('radial-two-stops', 24, 24, 'radial', 'pad', (12, 12, 10, 0), [(0.0, 'ffffff'), (1.0, '000000')], 2),
    ('radial-repeat', 24, 24, 'radial', 'repeat', (12, 12, 6, 0), [(0.0, 'ff8000'), (1.0, '0080ff')], 2),
    ('radial-reflect', 24, 24, 'radial', 'reflect', (12, 12, 6, 0), [(0.0, 'ff8000'), (1.0, '0080ff')], 2),
]


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def cairo_gradient(w, h, kind, spread, geo, stops):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    if kind == 'linear':
        pat = cairo.LinearGradient(*geo)
    else:
        pat = cairo.RadialGradient(geo[0], geo[1], 0, geo[0], geo[1], geo[2])
    for (at, col) in stops:
        pat.add_color_stop_rgb(at, *hex_rgb(col))
    pat.set_extend(EXTEND[spread])
    ctx.set_source(pat)
    ctx.paint()
    surf.flush()
    data = surf.get_data()
    stride = surf.get_stride()
    return [[(data[y * stride + x * 4 + 2], data[y * stride + x * 4 + 1], data[y * stride + x * 4])
             for x in range(w)] for y in range(h)]


def check_paint(probe):
    lines = []
    for (name, w, h, kind, spread, geo, stops, _b) in PAINT:
        lines.append('%s %d %d %s %s srgb %s %s' % (name, w, h, kind, spread,
                                                  ' '.join(repr(float(v)) for v in geo),
                                                  ' '.join('%s:%s' % (repr(float(a)), c) for a, c in stops)))
    got = parse(run_probe(probe, 'paint', '\n'.join(lines) + '\n'))
    failures = 0
    for (name, w, h, kind, spread, geo, stops, bound) in PAINT:
        want = cairo_gradient(w, h, kind, spread, geo, stops)
        rows = got.get(name, [])
        if len(rows) != h:
            print('FAIL %-26s the probe answered %d rows' % (name, len(rows)))
            failures += 1
            continue
        diffs = []
        for y in range(h):
            for x in range(w):
                ours = tuple(int(v) for v in rows[y][x].split(','))
                diffs.append(max(abs(a - b) for a, b in zip(ours, want[y][x])))
        # A hard stop puts one pixel column on either side of the edge, and which
        # colour the pixel centre on the edge takes is a rounding tie; the count
        # of pixels past the bound is what is checked there.
        worst = max(diffs)
        if name == 'linear-hard-stop':
            past = sum(1 for d in diffs if d > 2)
            ok = past <= 2 * h
            print('%s %-26s %d pixels past 2 levels (bound %d)' % ('ok  ' if ok else 'FAIL', name, past, 2 * h))
        else:
            ok = worst <= 1
            print('%s %-26s largest %3d (bound 1)' % ('ok  ' if ok else 'FAIL', name, worst))
        failures += 0 if ok else 1
    print('paint: %d scenarios, %d past their bound' % (len(PAINT), failures))
    return failures


# ---- cairo: blend modes ----

OPERATORS = {'source-over': cairo.OPERATOR_OVER, 'copy': cairo.OPERATOR_SOURCE,
             'source-in': cairo.OPERATOR_IN, 'source-out': cairo.OPERATOR_OUT,
             'plus-lighter': cairo.OPERATOR_ADD, 'multiply': cairo.OPERATOR_MULTIPLY,
             'screen': cairo.OPERATOR_SCREEN, 'overlay': cairo.OPERATOR_OVERLAY,
             'darken': cairo.OPERATOR_DARKEN, 'lighten': cairo.OPERATOR_LIGHTEN,
             'difference': cairo.OPERATOR_DIFFERENCE}

PIXELS = [(200, 100, 50, 255), (30, 220, 90, 255), (255, 255, 255, 255), (0, 0, 0, 255),
          (200, 100, 50, 128), (30, 220, 90, 64), (250, 10, 130, 200), (255, 255, 255, 0)]


def cairo_blend(op, s, d):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surf)
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.set_source_rgba(d[0] / 255, d[1] / 255, d[2] / 255, d[3] / 255)
    ctx.paint()
    ctx.set_operator(OPERATORS[op])
    ctx.set_source_rgba(s[0] / 255, s[1] / 255, s[2] / 255, s[3] / 255)
    ctx.paint()
    surf.flush()
    b, g, r, a = surf.get_data()[:4]
    return (r, g, b, a)


def premultiplied(p):
    return tuple(int(round(p[i] * p[3] / 255)) for i in range(3)) + (p[3],)


def check_blend(probe):
    cases = [(op, s, d) for op in OPERATORS for s in PIXELS for d in PIXELS]
    lines = ['%d %s %s %s' % (i, op, ' '.join(map(str, s)), ' '.join(map(str, d)))
             for i, (op, s, d) in enumerate(cases)]
    out = run_probe(probe, 'blend', '\n'.join(lines) + '\n').splitlines()
    worst = {}
    for line, (op, s, d) in zip(out, cases):
        ours = premultiplied(tuple(int(v) for v in line.split()[1:5]))
        theirs = cairo_blend(op, s, d)
        worst[op] = max(worst.get(op, 0), max(abs(a - b) for a, b in zip(ours, theirs)))
    failures = 0
    for op, w in worst.items():
        ok = w <= 2
        failures += 0 if ok else 1
        print('%s blend %-14s largest %d premultiplied levels over %d pairs (bound 2)'
              % ('ok  ' if ok else 'FAIL', op, w, len(PIXELS) ** 2))
    print('blend: %d modes, %d past their bound' % (len(worst), failures))
    return failures


# ---- Oklab, from the published formulas ----

def srgb_to_linear(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def linear_to_srgb(v):
    v = min(max(v, 0.0), 1.0)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def to_oklab(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def from_oklab(lab):
    l_, m_, s_ = (lab[0] + 0.3963377774 * lab[1] + 0.2158037573 * lab[2],
                  lab[0] - 0.1055613458 * lab[1] - 0.0638541728 * lab[2],
                  lab[0] - 0.0894841775 * lab[1] - 1.2914855480 * lab[2])
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (linear_to_srgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            linear_to_srgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            linear_to_srgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


OKLAB = [('ff0000', '00ff00'), ('0000ff', 'ffff00'), ('102030', 'f0e0d0'), ('ffffff', '000000')]


def check_oklab(probe):
    w = 17
    lines = ['ok%d %d 1 linear pad oklab 0.0 0.0 %d.0 0.0 0.0:%s 1.0:%s' % (i, w, w, a, b)
             for i, (a, b) in enumerate(OKLAB)]
    got = parse(run_probe(probe, 'paint', '\n'.join(lines) + '\n'))
    failures = 0
    for i, (a, b) in enumerate(OKLAB):
        la, lb = to_oklab(hex_rgb(a)), to_oklab(hex_rgb(b))
        worst = 0
        for x in range(w):
            t = (x + 0.5) / w
            lab = tuple(la[k] + (lb[k] - la[k]) * t for k in range(3))
            want = [int(round(c * 255)) for c in from_oklab(lab)]
            ours = [int(v) for v in got['ok%d' % i][0][x].split(',')]
            worst = max(worst, max(abs(p - q) for p, q in zip(ours, want)))
        ok = worst <= 1
        failures += 0 if ok else 1
        print('%s oklab %s to %s  largest %d (bound 1)' % ('ok  ' if ok else 'FAIL', a, b, worst))
    print('oklab: %d ramps, %d past their bound' % (len(OKLAB), failures))
    return failures


# ---- FreeType: glyphs ----

FONTS = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/truetype/lato/Lato-Regular.ttf',
         '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf']
GLYPH_TEXT = 'Hegj@&Q%'
GLYPH_SIZES = [12, 16, 33]


def check_glyph(probe):
    failures = 0
    runs = 0
    for font in FONTS:
        if not os.path.exists(font):
            continue
        for px in GLYPH_SIZES:
            out = subprocess.run([probe, 'glyph', font, GLYPH_TEXT, str(px)], capture_output=True,
                                 text=True).stdout
            face = ftglyph.open_face(font, px)
            worst, means, wrong_box = 0, [], 0
            lines = out.splitlines()
            i = 0
            while i < len(lines):
                gid = int(lines[i][4:])
                left, top, w, h = (int(v) for v in lines[i + 1].split())
                rows = [[int(v) for v in lines[i + 2 + r].split()] for r in range(h)]
                i += 2 + h
                fl, ft_top, fw, fh, frows, _adv = ftglyph.render_glyph(face, gid)
                # Both planes on one grid: x to the right of the pen, y down from the baseline.
                x0, x1 = min(left, fl), max(left + w, fl + fw)
                y0, y1 = min(-top, -ft_top), max(-top + h, -ft_top + fh)
                total, count, big = 0, 0, 0
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        a = rows[y + top][x - left] if 0 <= y + top < h and 0 <= x - left < w else 0
                        b = frows[y + ft_top][x - fl] if 0 <= y + ft_top < fh and 0 <= x - fl < fw else 0
                        d = abs(a - b)
                        total += d
                        count += 1
                        big = max(big, d)
                worst = max(worst, big)
                means.append(total / max(count, 1))
                if abs(left - fl) > 1 or abs(top - ft_top) > 1 or abs(w - fw) > 2 or abs(h - fh) > 2:
                    wrong_box += 1
            runs += 1
            mean = sum(means) / len(means)
            # FreeType flattens curves more coarsely than the tolerance asked here, so
            # its edge pixels differ by a few levels; the mean says the shapes agree.
            ok = mean <= 3.0 and worst <= 32 and wrong_box == 0
            failures += 0 if ok else 1
            print('%s glyph %-34s %2dpx  largest %3d  mean %.3f  boxes off %d'
                  % ('ok  ' if ok else 'FAIL', os.path.basename(font), px, worst, mean, wrong_box))
    print('glyph: %d font sizes, %d past their bound' % (runs, failures))
    return failures


CHECKS = {'fill': check_fill, 'stroke': check_stroke, 'paint': check_paint, 'blend': check_blend, 'oklab': check_oklab, 'glyph': check_glyph}


def main():
    probe = sys.argv[1]
    names = sys.argv[2:] or list(CHECKS)
    failures = sum(CHECKS[n](probe) for n in names)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
