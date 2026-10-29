# ftglyph.py - a glyph rendered by FreeType: unhinted, at a whole pixel size,
# with the pen on the pixel grid.
import ctypes
from ctypes import (c_void_p, c_int, c_long, c_short, c_ushort, c_uint, c_ubyte, c_char_p, POINTER,
                    Structure, byref)
import freetype

ft = freetype.ft


class Generic(Structure):
    _fields_ = [('data', c_void_p), ('finalizer', c_void_p)]


class BBox(Structure):
    _fields_ = [('xMin', c_long), ('yMin', c_long), ('xMax', c_long), ('yMax', c_long)]


class GlyphMetrics(Structure):
    _fields_ = [('width', c_long), ('height', c_long), ('horiBearingX', c_long), ('horiBearingY', c_long),
                ('horiAdvance', c_long), ('vertBearingX', c_long), ('vertBearingY', c_long),
                ('vertAdvance', c_long)]


class GlyphSlot(Structure):
    _fields_ = [('library', c_void_p), ('face', c_void_p), ('next', c_void_p), ('glyph_index', c_uint),
                ('generic', Generic), ('metrics', GlyphMetrics), ('linearHoriAdvance', c_long),
                ('linearVertAdvance', c_long), ('advance', freetype.Vector), ('format', c_int),
                ('bitmap', freetype.Bitmap), ('bitmap_left', c_int), ('bitmap_top', c_int)]


class Face(Structure):
    _fields_ = [('num_faces', c_long), ('face_index', c_long), ('face_flags', c_long),
                ('style_flags', c_long), ('num_glyphs', c_long), ('family_name', c_char_p),
                ('style_name', c_char_p), ('num_fixed_sizes', c_int), ('available_sizes', c_void_p),
                ('num_charmaps', c_int), ('charmaps', c_void_p), ('generic', Generic), ('bbox', BBox),
                ('units_per_EM', c_ushort), ('ascender', c_short), ('descender', c_short),
                ('height', c_short), ('max_advance_width', c_short), ('max_advance_height', c_short),
                ('underline_position', c_short), ('underline_thickness', c_short),
                ('glyph', POINTER(GlyphSlot))]


ft.FT_New_Face.argtypes = [c_void_p, c_char_p, c_long, POINTER(POINTER(Face))]
ft.FT_Set_Pixel_Sizes.argtypes = [POINTER(Face), c_uint, c_uint]
ft.FT_Load_Glyph.argtypes = [POINTER(Face), c_uint, c_int]
ft.FT_Render_Glyph.argtypes = [POINTER(GlyphSlot), c_int]

LOAD_NO_HINTING = 0x2
LOAD_NO_BITMAP = 0x8


def open_face(path, px):
    face = POINTER(Face)()
    if ft.FT_New_Face(freetype._lib, path.encode(), 0, byref(face)):
        raise RuntimeError('cannot open ' + path)
    ft.FT_Set_Pixel_Sizes(face, 0, px)
    return face


def render_glyph(face, glyph_id):
    """(left, top, width, height, rows, advance_26_6): left and top as FreeType
    states them, top being the rows above the baseline."""
    if ft.FT_Load_Glyph(face, glyph_id, LOAD_NO_HINTING | LOAD_NO_BITMAP):
        raise RuntimeError('cannot load glyph %d' % glyph_id)
    slot = face.contents.glyph
    if ft.FT_Render_Glyph(slot, 0):
        raise RuntimeError('cannot render glyph %d' % glyph_id)
    bm = slot.contents.bitmap
    rows = [[bm.buffer[r * bm.pitch + c] for c in range(bm.width)] for r in range(bm.rows)]
    return (slot.contents.bitmap_left, slot.contents.bitmap_top, bm.width, bm.rows, rows,
            slot.contents.metrics.horiAdvance)
