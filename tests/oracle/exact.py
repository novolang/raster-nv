# exact.py - the exact area a path covers in each pixel, by clipping the
# finely flattened outline against the pixel and summing signed areas.
#
# A model rather than a library: it shares no code and no algorithm with
# rasterfill's scanline accumulation, and it is the reference for curves,
# where FreeType's own flattening is coarser than the answer being tested.
# It reads coverage the way rasterfill does, from the signed area of the
# clipped outline: non-zero is the magnitude held at 1, even-odd is the
# magnitude folded back at every whole number.
import math

STEPS = 400


def flatten(commands):
    """Subpaths of points; every contour closed, curves in STEPS pieces."""
    runs = []
    cur = None
    pen = (0.0, 0.0)
    for c in commands:
        k = c[0]
        if k == 'M':
            if cur and len(cur) > 1:
                runs.append(cur)
            cur = [(c[1], c[2])]
            pen = (c[1], c[2])
        elif k == 'L':
            cur.append((c[1], c[2]))
            pen = (c[1], c[2])
        elif k == 'Q':
            for i in range(1, STEPS + 1):
                t = i / STEPS
                u = 1 - t
                cur.append((u * u * pen[0] + 2 * u * t * c[1] + t * t * c[3],
                            u * u * pen[1] + 2 * u * t * c[2] + t * t * c[4]))
            pen = (c[3], c[4])
        elif k == 'C':
            for i in range(1, STEPS + 1):
                t = i / STEPS
                u = 1 - t
                cur.append((u ** 3 * pen[0] + 3 * u * u * t * c[1] + 3 * u * t * t * c[3] + t ** 3 * c[5],
                            u ** 3 * pen[1] + 3 * u * u * t * c[2] + 3 * u * t * t * c[4] + t ** 3 * c[6]))
            pen = (c[5], c[6])
        elif k == 'Z':
            if cur and len(cur) > 1:
                runs.append(cur)
            cur = None
    if cur and len(cur) > 1:
        runs.append(cur)
    return runs


def clip_half(poly, inside, cross):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ia, ib = inside(a), inside(b)
        if ia:
            out.append(a)
        if ia != ib:
            out.append(cross(a, b))
    return out


def clip_box(poly, x0, y0, x1, y1):
    def cx(v):
        return lambda a, b: (v, a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]))

    def cy(v):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]), v)
    for inside, cross in ((lambda p: p[0] >= x0, cx(x0)), (lambda p: p[0] <= x1, cx(x1)),
                          (lambda p: p[1] >= y0, cy(y0)), (lambda p: p[1] <= y1, cy(y1))):
        if not poly:
            return poly
        poly = clip_half(poly, inside, cross)
    return poly


def area(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        s += a[0] * b[1] - b[0] * a[1]
    return s / 2


def render(commands, width, height, even_odd=False):
    runs = flatten(commands)
    boxes = [(min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r))
             for r in runs]
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            total = 0.0
            for r, (bx0, by0, bx1, by1) in zip(runs, boxes):
                if bx1 <= x or bx0 >= x + 1 or by1 <= y or by0 >= y + 1:
                    # Wholly outside the pixel's column or row: it adds nothing,
                    # unless it wraps the pixel entirely, which the clip finds.
                    if not (bx0 <= x and bx1 >= x + 1 and by0 <= y and by1 >= y + 1):
                        continue
                total += area(clip_box(r, x, y, x + 1, y + 1))
            v = abs(total)
            if even_odd:
                v = v % 2.0
                v = 2.0 - v if v > 1 else v
            else:
                v = min(v, 1.0)
            row.append(int(v * 255 + 0.5))
        rows.append(row)
    return rows
