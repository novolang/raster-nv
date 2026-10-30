#!/usr/bin/env python3
# vectors.py - the expected answers the unit suites embed, computed here by
# an independent model: numpy for the mask arithmetic, exact.py for the area
# a fill covers, and FreeType and cairo where the comparison scripts use them.
#
# usage: vectors.py NAME     prints Novo functions that answer hex strings.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import exact


def fn(name, hexstr):
    return 'fn %s() -> Str\n    "%s"\n' % (name, hexstr)


def hexof(a):
    return bytes(int(v) for v in np.asarray(a).reshape(-1)).hex()


def masks():
    rng = np.random.default_rng(20261030)
    a = rng.integers(0, 256, size=(4, 5), dtype=np.int64)
    b = rng.integers(0, 256, size=(4, 5), dtype=np.int64)
    b[0, :] = [0, 255, 128, 127, 129]
    out = [fn('mask_a', hexof(a)), fn('mask_b', hexof(b)),
           fn('want_min', hexof(np.minimum(a, b))), fn('want_max', hexof(np.maximum(a, b))),
           fn('want_subtract', hexof(np.minimum(a, 255 - b))), fn('want_invert', hexof(255 - a)),
           fn('want_threshold_100', hexof(np.where(a >= 100, 255, 0))),
           fn('want_threshold_128', hexof(np.where(a >= 128, 255, 0))),
           fn('want_scale_quarter', hexof(np.floor(a * 0.25 + 0.5)))]
    # Row-major bits, most significant first, rows padded to a byte: numpy.packbits.
    bits = (a >= 128).astype(np.uint8)
    out.append(fn('want_packed', np.packbits(bits, axis=1).tobytes().hex()))
    return out


def fills():
    out = []

    def poly(pts):
        return [('M',) + pts[0]] + [('L',) + p for p in pts[1:]] + [('Z',)]

    def star(order):
        import math
        pts = [(round(8 + 7 * math.cos(-math.pi / 2 + i * 2 * math.pi * order / 5), 3),
                round(8 + 7 * math.sin(-math.pi / 2 + i * 2 * math.pi * order / 5), 3)) for i in range(5)]
        return poly(pts)

    K = 0.5522847498

    def circle(cx, cy, r):
        k = K * r
        return [('M', cx + r, cy), ('C', cx + r, cy + k, cx + k, cy + r, cx, cy + r),
                ('C', cx - k, cy + r, cx - r, cy + k, cx - r, cy),
                ('C', cx - r, cy - k, cx - k, cy - r, cx, cy - r),
                ('C', cx + k, cy - r, cx + r, cy - k, cx + r, cy), ('Z',)]

    out.append(fn('want_triangle', hexof(exact.render(poly([(1.5, 1.25), (10.75, 3.5), (4.25, 10.5)]), 12, 12))))
    out.append(fn('want_diagonal', hexof(exact.render(poly([(0, 0), (8, 0), (0, 8)]), 8, 8))))
    out.append(fn('want_rect', hexof(exact.render(poly([(1.5, 1.5), (6.5, 1.5), (6.5, 5.25), (1.5, 5.25)]), 8, 8))))
    out.append(fn('want_star_nonzero', hexof(exact.render(star(2), 16, 16))))
    out.append(fn('want_star_evenodd', hexof(exact.render(star(2), 16, 16, even_odd=True))))
    out.append(fn('want_clipped', hexof(exact.render(poly([(-4.5, 2.25), (9.5, 3), (6.25, 14), (-2, 8)]), 8, 8))))
    out.append(fn('want_circle', hexof(exact.render(circle(8, 8, 6.5), 16, 16))))
    out.append(fn('want_ring', hexof(exact.render(circle(8, 8, 7) + list(reversed_circle(8, 8, 3.5)), 16, 16))))
    tri = [(0.5, 0.5), (5, 1), (2, 4.5)]
    rot = [(10 - y, x) for (x, y) in tri]
    out.append(fn('want_rotated', hexof(exact.render(poly(rot), 12, 12))))
    scaled = [(2 * x + 1, 1.5 * y + 2) for (x, y) in tri]
    out.append(fn('want_scaled', hexof(exact.render(poly(scaled), 12, 12))))
    out.append(fn('want_quad', hexof(exact.render([('M', 1, 11), ('Q', 6, -3, 11, 11), ('Z',)], 12, 12))))
    return out


def reversed_circle(cx, cy, r):
    k = 0.5522847498 * r
    return [('M', cx + r, cy), ('C', cx + r, cy - k, cx + k, cy - r, cx, cy - r),
            ('C', cx - k, cy - r, cx - r, cy - k, cx - r, cy),
            ('C', cx - r, cy + k, cx - k, cy + r, cx, cy + r),
            ('C', cx + k, cy + r, cx + r, cy + k, cx + r, cy), ('Z',)]


def strokes():
    import cairo
    import compare as c
    out = []

    def a8(w, h, width, cap, join, miter, off, dashes, cmds):
        def draw(ctx):
            ctx.set_line_width(width)
            ctx.set_line_cap(c.CAPS[cap])
            ctx.set_line_join(c.JOINS[join])
            ctx.set_miter_limit(miter)
            if dashes:
                ctx.set_dash(dashes, off)
            c.trace(ctx, cmds)
            ctx.set_source_rgba(0, 0, 0, 1)
            ctx.stroke()
        return hexof(c.cairo_a8(w, h, draw))

    corner = c.poly([(3, 13), (3, 4), (12, 4)], False)
    out.append(fn('want_miter_corner', a8(16, 16, 3.0, 'b', 'm', 4.0, 0.0, [], corner)))
    out.append(fn('want_bevel_corner', a8(16, 16, 3.0, 'b', 'b', 4.0, 0.0, [], corner)))
    out.append(fn('want_closed_square', a8(16, 16, 2.0, 'b', 'm', 4.0, 0.0, [], c.poly([(3, 3), (12, 3), (12, 12), (3, 12)]))))
    out.append(fn('want_dashed', a8(20, 6, 2.0, 'b', 'm', 4.0, 1.0, [4.0, 3.0], c.poly([(1, 3), (19, 3)], False))))
    out.append(fn('want_square_caps', a8(16, 8, 3.0, 's', 'm', 4.0, 0.0, [], c.poly([(4.5, 4), (11.5, 4)], False))))
    out.append(fn('want_slanted', a8(16, 16, 2.5, 'b', 'm', 4.0, 0.0, [], c.poly([(2, 3), (13, 12)], False))))
    return out


def paints():
    import compare as c
    out = []

    def rgb_hex(rows):
        return bytes(v for row in rows for px in row for v in px).hex()

    red_blue = [(0.0, 'ff0000'), (1.0, '0000ff')]
    out.append(fn('want_linear_pad', rgb_hex(c.cairo_gradient(16, 1, 'linear', 'pad', (2, 0, 14, 0), red_blue))))
    out.append(fn('want_linear_repeat', rgb_hex(c.cairo_gradient(16, 1, 'linear', 'repeat', (2, 0, 6, 0), red_blue))))
    out.append(fn('want_linear_reflect', rgb_hex(c.cairo_gradient(16, 1, 'linear', 'reflect', (2, 0, 6, 0), red_blue))))
    out.append(fn('want_three_stops', rgb_hex(c.cairo_gradient(
        16, 1, 'linear', 'pad', (0, 0, 16, 0), [(0.0, 'ff0000'), (0.25, '00ff00'), (1.0, '0000ff')]))))
    out.append(fn('want_radial', rgb_hex(c.cairo_gradient(8, 8, 'radial', 'pad', (4, 4, 4, 0),
                                                         [(0.0, 'ffffff'), (1.0, '102030')]))))
    out.append(fn('want_diagonal', rgb_hex(c.cairo_gradient(8, 8, 'linear', 'pad', (1, 1, 7, 6),
                                                           [(0.0, 'ffff00'), (1.0, '102030')]))))
    # Oklab, from the published formulas, across nine pixel centres of a ramp from red to green.
    a, b = c.to_oklab(c.hex_rgb('ff0000')), c.to_oklab(c.hex_rgb('00ff00'))
    row = []
    for x in range(9):
        t = (x + 0.5) / 9
        lab = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
        row.append(tuple(int(round(v * 255)) for v in c.from_oklab(lab)))
    out.append(fn('want_oklab', rgb_hex([row])))
    return out


def blends():
    import compare as c
    lines = []
    picks = [((200, 100, 50, 255), (30, 220, 90, 255)), ((200, 100, 50, 128), (30, 220, 90, 255)),
             ((30, 220, 90, 64), (250, 10, 130, 200)), ((250, 10, 130, 200), (255, 255, 255, 0)),
             ((255, 255, 255, 255), (0, 0, 0, 128))]
    for op in c.OPERATORS:
        for (s, d) in picks:
            r = c.cairo_blend(op, s, d)
            lines.append('%s %s %s %s' % (op, ' '.join(map(str, s)), ' '.join(map(str, d)), ' '.join(map(str, r))))
    return [fn('want_blends', '\\n'.join(lines))]


def draws():
    import cairo
    import compare as c

    def rgb_hex(surface_rows):
        return bytes(v for row in surface_rows for px in row for v in px).hex()

    def render(w, h, bg, fg, op, cmds):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surf)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(*[v / 255 for v in bg])
        ctx.paint()
        ctx.set_operator(c.OPERATORS[op])
        ctx.set_source_rgba(*[v / 255 for v in fg])
        c.trace(ctx, cmds)
        ctx.fill()
        surf.flush()
        data = surf.get_data()
        stride = surf.get_stride()
        return [[(data[y * stride + x * 4 + 2], data[y * stride + x * 4 + 1], data[y * stride + x * 4])
                 for x in range(w)] for y in range(h)]

    rect = c.poly([(1.5, 1.5), (10.25, 1.5), (10.25, 8.75), (1.5, 8.75)])
    tri = c.poly([(1.25, 1.5), (10.5, 2.25), (5.5, 10.75)])
    return [fn('want_over_rect', rgb_hex(render(12, 12, (250, 240, 30, 255), (0, 90, 200, 128), 'source-over', rect))),
            fn('want_multiply_triangle', rgb_hex(render(12, 12, (250, 200, 100, 255), (60, 140, 255, 255), 'multiply', tri))),
            fn('want_screen_rect', rgb_hex(render(12, 12, (20, 60, 100, 255), (220, 180, 40, 160), 'screen', rect))),
            fn('want_copy_rect', rgb_hex(render(12, 12, (255, 255, 255, 255), (30, 150, 90, 255), 'copy', rect)))]


if __name__ == '__main__':
    which = sys.argv[1]
    print('\n'.join({'masks': masks, 'fills': fills, 'strokes': strokes, 'paints': paints, 'blends': blends, 'draws': draws}[which]()))
