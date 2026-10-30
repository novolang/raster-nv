# raster-nv

A **rasteriser** turns a path — the outline a font or a drawing
describes — into pixels. This one is a software rasteriser for
novo-lang. It does the job in two steps rather than one: a path becomes
a **coverage mask**, which says how much of each pixel the shape covers
and nothing about colour, and a separate compositing step puts a colour
through that mask into an image the caller owns. The vocabulary — fill
rules, joins, caps, dashes, gradients — is
[SVG 2](https://www.w3.org/TR/SVG2/painting.html)'s, and the reference
implementation is [tiny-skia](https://github.com/RazrFalcon/tiny-skia).
It is built on
[geometry-nv](https://novo-lang.org/packages/geometry-nv),
[svg-nv](https://novo-lang.org/packages/svg-nv),
[color-nv](https://novo-lang.org/packages/color-nv),
[image-nv](https://novo-lang.org/packages/image-nv) and
[font-nv](https://novo-lang.org/packages/font-nv).

## What it is

A rasteriser's real output is the answer to one question per pixel: how
much of this pixel does the shape cover? The answer is a number from 0
to 255, and it knows nothing about what colour the shape is. A
**coverage mask** is a plane of those numbers, one byte per pixel,
row-major with no padding. `RstMask` is that value, and the rest of the
package follows from having it.

A mask carries the rectangle it covers, not the whole image. A path's
coverage is zero almost everywhere, so a mask covers the path's
bounding box clipped to the target, and `origin_x` and `origin_y` say
where that box sits. Eight bits rather than sixteen, because a byte is
what a composite against an 8-bit image can use without rounding twice,
it is what every font atlas stores, and it makes a 1024-square mask one
megabyte instead of four.

**Anti-aliasing** is what makes a diagonal edge look smooth instead of
stepped, and there are two ways to compute it. Supersampling asks "is
the shape here?" at sixteen points inside the pixel and counts the
answers: sixteen times the work, and coverage quantised to seventeen
levels, which shows as banding on a shallow edge. The **analytic**
method integrates the exact area the edges cut out of each pixel: one
pass, and exact answers. This rasteriser is analytic, which is a claim
with a number attached — a 45-degree edge through the centre of a pixel
covers exactly half of it, and the coverage is 128, not about 128.
`rasterfill.exact_coverage_is_claimed` is that promise as a function a
test can read.

A **fill rule** decides which parts of a self-overlapping path are
inside it. Non-zero counts the directions the path crosses a ray and
fills where the total is not zero; even-odd counts crossings and fills
where the count is odd. They are geometry-nv's `GeomFillRule`, the same
two SVG names.

A **stroke** — the line drawn along a path — is here a path-to-path
operation. `rasterstroke.outline` answers another path, which can be
measured, hit-tested, written out, or stroked again. Dashing is also
path-to-path, so the two compose, in the order SVG gives: dash first,
then stroke.

| How a corner is turned | What it does |
| --- | --- |
| `RstMiter` | Extends both edges until they meet, falling back to a bevel when the spike would be longer than the miter limit |
| `RstRound` | Fills the wedge with an arc |
| `RstBevel` | Cuts straight across |

| How an end is finished | What it does |
| --- | --- |
| `RstButt` | Stops at the endpoint, so a zero-length subpath draws nothing |
| `RstRoundCap` | A half-disc past the endpoint, so a zero-length subpath draws a dot |
| `RstSquare` | A half-square past the endpoint, extending by half the width |

A **paint** says what colour a covered pixel gets. It is one value with
four cases: a solid colour, a linear ramp along a segment, a radial
ramp from a centre, and a sweep ramp around a centre. Each gradient
carries its stops, the colour space its stops are interpolated in, and
what it does outside its own span — pad, repeat, or reflect.

A **blend mode** says how the source colour is combined with what is
already in the image. Eleven are offered: source-over, source-copy,
source-in, source-out, plus, multiply, screen, overlay, darken, lighten
and difference. Source-in and source-out are the Porter-Duff operators
of those names. The others are the separable blend functions of the W3C
Compositing and Blending specification, and plus adds the two and clamps.

Blending is done on the stored values, premultiplied, as cairo, pixman
and tiny-skia do it. A pixel half covered by black on white is 127.
Blending in linear light would give 188, which is what color-nv's
`colormix.over` does.

| Quantity | Value |
| --- | --- |
| Coverage per pixel | one byte, 0 to 255 |
| Coverage of a 45-degree edge through a pixel's centre | exactly 128 |
| Default mask budget | 64 Mi pixels, which is 8192 by 8192 and 64 MB |
| Default edge budget | 1 Mi edges for one path |
| Default flattening tolerance | 0.25 pixels, at most 256 segments per curve |
| Default miter limit | 4.0, which is SVG's |
| Default gradient interpolation space | Oklab |
| Subpixel positions a glyph cache distinguishes | 3 |
| Glyph size in a cache key | 1/64ths of a pixel, so 16 pixels is 1024 |
| Packed 1-bit stride | `(width + 7) / 8` bytes, most significant bit leftmost |

No function in this package performs input or output. Nothing is
opened, nothing is written, no clock is read, and every output buffer
belongs to the caller.

## Install

```
novo pkg add raster-nv
```

## Example

A filled and outlined rectangle drawn into an image the program
allocated, and the blue channel of two pixels read back. The program
prints `255 127`.

```novo
use geomrect
use geomxform
use image
use srgb
use svgpath
use rasterdraw
use rasterpaint
use rasterstroke

fn main() [io]
    // A white image 16 pixels across and 8 high. The package never holds it.
    let img = image.filled(16, 8, PixRgba8, srgb.opaque(srgb.white()))

    // The clip is the whole image, the blend is source-over, the budgets are the defaults.
    let o = rasterdraw.opts(16, 8)

    // A rectangle from (2, 1) to (13.5, 6), as a path.
    let bar = svgpath.of_rect(geomrect.of_xywh(2.0, 1.0, 11.5, 5.0), 0.0, 0.0)

    // The fill. The image goes in and a new one comes back.
    let blue = srgb.rgb8(0, 0, 255)
    let filled = rasterdraw.fill_path(img, bar, rasterpaint.solid(blue), GeomNonZero,
                                      geomxform.identity(), o)!

    // The outline, one unit wide, in black.
    let outlined = rasterdraw.stroke_path(filled, bar, rasterpaint.solid(srgb.black()),
                                          rasterstroke.solid(1.0), geomxform.identity(), o)!

    // The middle is blue, and a pixel on the edge is half way to black.
    let middle = image.pixel(outlined, 7, 3) ?? srgb.transparent()
    let edge = image.pixel(outlined, 2, 3) ?? srgb.transparent()
    println("${middle.rgb.b} ${edge.rgb.b}")
```

## What the package contains

| Module | Contents |
| --- | --- |
| `rastermask` | The coverage mask, its budget, reading it, combining two of them, and turning one into a bit per pixel. |
| `rasterfill` | The scanline sweep: a path and a transform in, a coverage mask out. Also the flattening settings, a bounding box, an edge count, and a point-in-path test. |
| `rasterstroke` | Joins, caps and the stroke style; the outline of a stroke as a path; dashing as a path; and the arithmetic for a miter. |
| `rasterpaint` | The four paints, the eleven blend modes, the gradient spread, the colour at a point, and the blend itself on one pixel or on one packed integer. |
| `rasterdraw` | Compositing a mask into an image, and the four calls a renderer makes: fill a path, stroke a path, fill a rectangle, draw an image. Also the conversions between a mask and a greyscale image. |
| `rasterglyph` | A glyph cache the caller holds, keyed on integers, holding masks rather than pixels; rasterising one glyph; and drawing a whole shaped run. |
| `rastererror` | The six things a rasteriser refuses, and a line a person can read. |

## How to choose an entry point

**`rasterdraw.fill_path` and `rasterdraw.stroke_path` are what a
renderer calls.** Each takes the image, the path, a paint and the
options, and answers the image.

**`rasterdraw.composite` is the call the others are written on.** It
takes any mask and puts a paint through it. It is public because a mask
can come from somewhere else — a decoded image's alpha channel, a blur,
the mask from the last frame — and all of them composite through the
same loop.

**`rasterfill.fill` answers the mask itself**, for a caller that wants
to keep it, combine it, or use it as a clip.

**`rasterstroke.outline` and `rasterstroke.dash` answer paths.** Use
them when the stroke is to be inspected or transformed rather than
drawn immediately.

**`rasterglyph.draw_run` draws a whole shaped run in one pass**, and
`rasterglyph.rasterize_cached` is the one-glyph form that hands the
cache back.

**`rasterfill.fill_rect` and `rasterfill.fill_convex` are the fast
paths.** A rectangle needs no edge list, and a convex polygon needs no
winding accumulation.

## The rules a user needs

1. **Coverage is the value, and the colour arrives later.** One
   rasterisation serves every colour the shape is ever drawn in. That
   is why a glyph cache here holds masks: a terminal drawing the same
   `e` in sixteen colours rasterises it once.
2. **A clip is a mask.** Clipping to a shape is `rastermask.intersect`
   of two masks, so a clip is anti-aliased for free and a clip to a
   rotated rectangle is not a special case.
   `rasterdraw.with_clip` puts one in the options.
3. **`intersect` is a pixel-wise minimum, not a multiply.** Two masks
   that each cover a pixel fully leave it fully covered. A multiply
   would not quite.
4. **Two masks combine only when their rectangles match.**
   `rastermask.same_extent` is the check and `RstExtentMismatch` is
   what skipping it costs. `rastermask.retarget` is the one place a
   mismatch is repaired, by a caller that asked for it by name.
5. **A mask's `at` takes target coordinates, not mask coordinates.**
   That is what a compositor and a hit test both have.
   `rastermask.row` is the exception and is in mask coordinates,
   because a caller walking rows is walking the mask.
6. **The pixel box is rounded outward.** A pixel a curve touches by a
   hundredth still has coverage, and rounding inward would shave a
   pixel off the edge of every shape. `rastermask.extent_for` is that
   arithmetic.
7. **The size crosses the interface before anything is allocated.** The
   numbers in a path come out of a file, and a file can ask for a
   petabyte. Every mask-producing call takes an `RstLimits`, and
   `RstTooLarge` carries both the size asked for and the limit.
   `rastermask.cost_of` lets a caller ask first.
8. **Most things that could go wrong are not refusals.** A path outside
   the mask is zero coverage. A zero-width stroke is the hairline case.
   A gradient with one stop is a solid colour. What is refused is a
   request whose answer would not fit in memory or whose arithmetic has
   no meaning: the six cases in `RstFault`.
9. **A stroke's fill rule is not a choice.** A stroke outline's two
   offsets run in opposite directions, so an even-odd fill would hollow
   out every overlap — and an overlap is what a join is.
   `rasterstroke.fill_rule()` answers `GeomNonZero` as a value.
10. **A stroke of width 0 draws nothing**, which is what SVG says.
    PostScript and most plotting libraries draw one device pixel
    instead, and `rasterstroke.hairline()` is the call that asks for
    that reading.
11. **Dash before stroke.** `rasterstroke.dash` answers a path and
    `rasterstroke.outline` takes one, so the two chain in the order the
    specification gives. `rasterstroke.dash_is_usable` rejects a
    pattern that cannot advance, which is `RstBadDash`.
12. **A stroke reaches further than half its width at a sharp corner.**
    `rasterstroke.stroked_bounds` accounts for the miter, and
    `rasterstroke.miter_extent` is the arithmetic.
13. **The caller owns the image.** Every call in `rasterdraw` takes an
    `Image` and answers an `Image`. There is no surface, no context and
    no state carried between calls, so the package never holds a buffer
    and double buffering is the caller's.
14. **What would have been that state is `RstDrawOpts`**: the clip
    rectangle, an optional shaped clip, the blend mode, the transform
    applied to the paint alone, the flattening and the budget. It is a
    value, so a clip cannot be left set.
15. **The paint transform is separate from the shape transform.** They
    are two different matrices in every format that has gradients; the
    second is SVG's `gradientTransform`.
16. **Alpha is not premultiplied on the way in.** A half-transparent
    white is a white and not a grey. A paint's alpha multiplies the
    coverage rather than replacing it.
17. **Gradients interpolate in Oklab unless a caller says otherwise.**
    Interpolating red to green in encoded sRGB passes through brown.
    `rasterpaint.default_space()` is `SpaceOklab`, and every gradient
    takes the space as a field, so a caller reproducing an existing
    picture asks for `SpaceSrgb` by name.
18. **A glyph cache key is integers only.** The size is in 1/64ths of a
    pixel, because two keys have to compare equal and two floats
    computed by different routes do not — a cache keyed on a float
    misses every time and grows without bound. The font is a number the
    caller assigns, which is what stops two fonts' glyph 42 from
    colliding.
19. **`RstGlyphImage.bearing_y` is positive upward.** It is the one
    place in this package where y grows up, because that is how a
    font's ascent is measured.
20. **Check a shaped run against its outlines.**
    `rasterglyph.run_is_consistent` says whether the run and the list
    of outlines line up before anything is drawn.
21. **Not every pixel format can be drawn into.**
    `rasterdraw.kinds_supported` names the four that can and
    `rasterdraw.can_draw_into` is the check. `RstPixelKind` is the
    refusal. A 16-bit destination is the case that reaches it: an 8-bit
    mask against a 16-bit image would round coverage twice.
22. **`rasterdraw.draw_image` is nearest-neighbour at whole-pixel
    offsets.** Scaling and rotating an image is resampling, which
    image-nv does.
23. **Blending is on the stored values.** A pixel half covered by black
    on white is 127. `rasterpaint.blend_packed` takes a pixel as one
    integer, red in the highest byte and alpha in the lowest, and a
    coverage from 0 to 255, so a loop over a million pixels allocates
    nothing.
24. **A cached glyph is drawn at the left edge of its subpixel column.**
    A pen on a whole pixel is exact, and the others are at most a third
    of a pixel to the left of where they belong. The size in the key of
    a glyph drawn by `draw_run` is the scale's horizontal factor in
    65536ths, since a run carries font units and no em.
25. **A subpath of one point is a mark or nothing.** A round cap draws
    a disc, a square cap draws a square, and a butt cap draws nothing.
    A closed subpath of two points is a line with a join at each end.
26. **A dash pattern starts again at every subpath.** An odd pattern is
    used twice over, as SVG says, and a negative entry is refused.
27. **A gradient is sampled at the centre of each pixel**, in the
    paint's own coordinates, through the inverse of the paint transform.
    That is exact for every matrix. `rasterpaint.transformed` moves a
    paint exactly only for a rotation, a shift, a uniform scale and a
    mirror.
28. **One bit per pixel is a threshold and a packing.**
    `rastermask.threshold` turns coverage into 0 or 255 and
    `rastermask.pack_rows_1bit` packs the result eight pixels to a
    byte, most significant bit leftmost, which is what a monochrome
    panel controller and a 1-bit BMP expect. The bit order is published
    because a picture packed the other way looks like static.

## What is not included

- **Resampling.** Scaling and rotating an image is image-nv's job. See
  rule 22.
- **Blur, shadows and filter chains.** A filter chain is its own
  subject.
- **The two-circle radial gradient.** SVG allows a focal point inside a
  larger circle. It needs a different parameter solve, it is rare, and
  approximating it with a concentric gradient is a visible difference a
  caller cannot see coming, so it is absent rather than wrong.
- **16-bit destinations.** See rule 21.
- **Blending in linear light.** color-nv's `colormix.over` does it. See
  rule 23.
- **Joining a dash across the start of a closed subpath.** The first
  and the last dash of a closed subpath each end in a cap.
- **Hinting and stem darkening.** Hinting belongs with the font.
  Stem darkening is a decision about a caller's whole pipeline, and
  `rastermask.scale` is where a caller that wants it applies it.
- **Subpixel (LCD) anti-aliasing.** It is three coverage values per
  pixel instead of one, plus a filter to stop the colour fringing, so
  it would change `RstMask`'s shape.
- **Removing a stroke's self-intersections.** A tight curve's offset
  crosses itself, and the non-zero fill makes the result look right,
  which is what every 2D library does.
- **Threads.** Single-threaded by construction. Tiling is the caller's,
  and `rasterdraw.opts_at` is what it uses.
- **A rasteriser for a microcontroller.** The expensive part here is
  the edge list, the sort and the active-edge walk, and a one-bit
  output makes none of it cheaper — the mask is still a byte per pixel
  while it is being built. A device with a few kilobytes of memory
  needs a span filler over a fixed scanline buffer with integer
  coordinates and no edge list, which shares no code with this.

## Related packages

- [geometry-nv](https://novo-lang.org/packages/geometry-nv) has the
  transform, the rectangles, the polygon and the fill rule. The fill
  rule is shared rather than redeclared: even-odd and non-zero are the
  same two rules SVG names, and two enums with the same two variants
  would mean a caller converting between them.
- [svg-nv](https://novo-lang.org/packages/svg-nv) has `SvgPath`, which
  is what a path is here and what a font's outlines already are.
- [color-nv](https://novo-lang.org/packages/color-nv) has the colours,
  the gradient stops and the interpolation spaces. A gradient's stop
  list *is* `[ColorStop]`, which is what makes an Oklab gradient one
  argument rather than a second gradient type.
- [image-nv](https://novo-lang.org/packages/image-nv) has the `Image`
  this package draws into, and the resampling it does not do.
- [font-nv](https://novo-lang.org/packages/font-nv) reads a font file
  and answers outlines, metrics and a shaped run. `rasterglyph` is the
  only module that names it; every other module is reachable without
  it.
- [plot-nv](https://novo-lang.org/packages/plot-nv) turns a chart into
  a list of drawing operations, each of which is one of the four calls
  in `rasterdraw`.

## Reference implementations

tiny-skia is Skia's raster pipeline ported to Rust, and is the
reference for the whole shape, including keeping the clip mask separate
from the pixel buffer. Skia's own behaviour is the correctness
reference where the two disagree. Pillow's `ImageDraw` is the surface a
caller reaches for first.

One type is shared here that tiny-skia keeps apart: a clip and a
coverage mask are both `RstMask`, so combining them is one function
rather than two.

## Tests

```bash
novo test --isolate tests/rastermask_tests.nv     # the mask, its budget and its arithmetic
novo test --isolate tests/rastererror_tests.nv    # the six refusals
novo test --isolate tests/rasterfill_tests.nv     # the sweep and the fill rules
novo test --isolate tests/rasterstroke_tests.nv   # joins, caps, dashes and bounds
novo test --isolate tests/rasterpaint_tests.nv    # gradients and blend modes
novo test --isolate tests/rasterdraw_tests.nv     # compositing, clear, images
novo test --isolate tests/rasterglyph_tests.nv    # the glyph cache and runs
bash tests/coverage.sh                            # the line coverage over src/
bash tests/oracle/compare.sh                      # the comparison with cairo and FreeType
```

The coverage plane of a fill is checked against a model that clips the
finely flattened outline against each pixel and sums the signed areas,
and against FreeType's smooth rasteriser. Strokes, gradients, blend
modes and a filled path over a background are checked against cairo with
pixman. Oklab ramps are checked against the formulas Bjorn Ottosson
published, glyph masks against FreeType on installed fonts, and the mask
arithmetic against numpy. `tests/oracle/vectors.py` prints the expected
values the suites embed, and `tests/oracle/compare.sh` runs the wider
comparison and prints the largest difference of each scenario.

`rasterfill_tests.nv` asserts the claim the package is built on: that a
half-covered pixel is 128. It also uses a five-pointed star, which is
the shape where the two fill rules disagree, checks that the rectangle
fast path answers what the sweep would, and that a collapsing transform
is refused rather than drawn as nothing. `rastermask_tests.nv` asserts
that the size is checked before anything is allocated, that a clip is a
minimum and not a multiply, that two masks of different rectangles
refuse rather than guess, and that the pixel box is rounded outward.
`rasterstroke_tests.nv` asserts that a stroke is a path, that dashing
composes with stroking, and that a miter beyond the limit is a bevel.
`rasterpaint_tests.nv` asserts that a gradient interpolates in Oklab
unless asked otherwise. `rasterdraw_tests.nv` asserts that the caller
gets its image back and that the options are a value, so a clip cannot
be left set. `rasterglyph_tests.nv` asserts that a glyph taken from the
cache hands the cache back.

The line coverage over `src/` is 100%.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
