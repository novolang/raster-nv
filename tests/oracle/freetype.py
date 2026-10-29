# freetype.py - FreeType's smooth rasteriser through ctypes: a list of path
# commands in, an 8-bit coverage plane out.
#
# FreeType integrates the exact area an outline cuts out of each pixel, which
# is what raster-nv's rasterfill does, so the two agree to within the 1/64
# pixel grid FreeType rounds its input to.  Arcs have no FreeType form; a path
# given here holds only M, L, Q, C and Z.
import ctypes
from ctypes import c_void_p, c_int, c_long, c_short, c_char, c_ubyte, c_uint, c_ushort, POINTER, Structure, byref, cast

ft = ctypes.CDLL('libfreetype.so.6')

class Vector(Structure):
    _fields_ = [('x', c_long), ('y', c_long)]

class Outline(Structure):
    _fields_ = [('n_contours', c_short), ('n_points', c_short), ('points', POINTER(Vector)),
                ('tags', POINTER(c_char)), ('contours', POINTER(c_short)), ('flags', c_int)]

class Bitmap(Structure):
    _fields_ = [('rows', c_uint), ('width', c_uint), ('pitch', c_int), ('buffer', POINTER(c_ubyte)),
                ('num_grays', c_ushort), ('pixel_mode', c_ubyte), ('palette_mode', c_ubyte),
                ('palette', c_void_p)]

ft.FT_Init_FreeType.argtypes = [POINTER(c_void_p)]
ft.FT_Outline_Get_Bitmap.argtypes = [c_void_p, POINTER(Outline), POINTER(Bitmap)]

_lib = c_void_p()
ft.FT_Init_FreeType(byref(_lib))

EVEN_ODD = 0x2


def contours_of(commands):
    """Split [('M',x,y), ('L',x,y), ('Q',x1,y1,x,y), ('C',...), ('Z',)] into
    FreeType contours: lists of (x, y, tag), tag 1 on, 0 conic, 2 cubic."""
    out = []
    cur = None
    for c in commands:
        k = c[0]
        if k == 'M':
            if cur and len(cur) > 1:
                out.append(cur)
            cur = [(c[1], c[2], 1)]
        elif k == 'L':
            cur.append((c[1], c[2], 1))
        elif k == 'Q':
            cur.append((c[1], c[2], 0))
            cur.append((c[3], c[4], 1))
        elif k == 'C':
            cur.append((c[1], c[2], 2))
            cur.append((c[3], c[4], 2))
            cur.append((c[5], c[6], 1))
        elif k == 'Z':
            if cur and len(cur) > 1:
                out.append(cur)
            cur = None
    if cur and len(cur) > 1:
        out.append(cur)
    # FreeType closes a contour implicitly; a closing point equal to the start
    # is dropped so the closing segment is not doubled.
    fixed = []
    for cn in out:
        if len(cn) > 1 and cn[-1][2] == 1 and cn[-1][:2] == cn[0][:2]:
            cn = cn[:-1]
        fixed.append(cn)
    return fixed


def render(commands, width, height, even_odd=False):
    """Coverage rows (top row first) of the path on a width x height grid."""
    contours = contours_of(commands)
    pts = []
    tags = []
    ends = []
    for cn in contours:
        for (x, y, t) in cn:
            # FreeType's y grows upward; the grid here grows downward.
            pts.append(Vector(int(round(x * 64)), int(round((height - y) * 64))))
            tags.append(t)
        ends.append(len(pts) - 1)
    n = len(pts)
    if n == 0:
        return [[0] * width for _ in range(height)]
    parr = (Vector * n)(*pts)
    tarr = (c_char * n)(*[bytes([t]) for t in tags])
    carr = (c_short * len(ends))(*ends)
    outline = Outline(len(ends), n, cast(parr, POINTER(Vector)), cast(tarr, POINTER(c_char)),
                      cast(carr, POINTER(c_short)), EVEN_ODD if even_odd else 0)
    buf = (c_ubyte * (width * height))()
    bm = Bitmap(height, width, width, cast(buf, POINTER(c_ubyte)), 256, 2, 0, None)
    err = ft.FT_Outline_Get_Bitmap(_lib, byref(outline), byref(bm))
    if err:
        raise RuntimeError('FT_Outline_Get_Bitmap failed: %d' % err)
    rows = [list(buf[r * width:(r + 1) * width]) for r in range(height)]
    # With the y axis flipped on the way in, row 0 of the buffer is the top.
    return rows
