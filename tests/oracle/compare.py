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
import exact
import freetype

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
        toks = []
        for c in cmds:
            toks.append(c[0])
            toks.extend(repr(float(v)) for v in c[1:])
        lines.append('%s %d %d %s %s %s' % (name, w, h, rule, tol, ' '.join(toks)))
    return '\n'.join(lines) + '\n'


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


def main():
    probe = sys.argv[1]
    failures = 0
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        f.write(scenario_lines(FILL))
        path = f.name
    out = subprocess.run([probe, 'fill', path], capture_output=True, text=True).stdout
    os.unlink(path)
    got = parse(out)
    for (name, w, h, rule, tol, cmds, bound) in FILL:
        if name in EXACT:
            want = exact.render(cmds, w, h, even_odd=(rule == 'eo'))
        else:
            want = freetype.render(cmds, w, h, even_odd=(rule == 'eo'))
        rows = got.get(name, [])
        if len(rows) != h:
            print('FAIL %-22s the probe answered %d rows' % (name, len(rows)))
            failures += 1
            continue
        diffs = [abs(int(rows[y][x]) - want[y][x]) for y in range(h) for x in range(w)]
        worst, mean = max(diffs), sum(diffs) / len(diffs)
        ok = worst <= bound
        failures += 0 if ok else 1
        print('%s %-22s largest %3d (bound %d)  mean %.3f' % ('ok  ' if ok else 'FAIL', name, worst, bound, mean))
    print('fill: %d scenarios, %d past their bound' % (len(FILL), failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
