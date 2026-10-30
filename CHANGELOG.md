# Changelog

All notable changes to raster-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-10-29

The first implementation of the interface published as 0.0.3: every function
has a body. The package is measured against cairo, pixman, FreeType and numpy,
and the line coverage over `src/` is 100%.

### Breaking

These break code written against 0.0.x, or settle what the 0.0.x comments left
open.

- `rasterpaint.blend_over` and every blend mode work on the stored values,
  premultiplied, as cairo, pixman and tiny-skia do. The 0.0.x comment said
  `colormix.over` was the same operation. `colormix.over` blends in linear
  light, so the two differ wherever a pixel is partly covered or partly
  transparent.
- `RstSrcIn` and `RstSrcOut` are the Porter-Duff operators of those names, the
  source scaled by the destination's opacity and by its transparency. The 0.0.x
  comments described the destination operators under these names.
- `rastermask.same_extent` compares the origin as well as the size, and the
  combinations refuse two masks at different origins with `RstExtentMismatch`.
- `rastermask.mask` and `rastermask.full` panic for a width or a height below 1.
- `rasterfill.fill_convex` fills with the non-zero rule through the same sweep
  as `fill`. The answer is what `fill` gives for the same ring.
- `rasterstroke.hairline()` is a style with a negative width. `outline` and
  `stroked_bounds` treat it as one path unit wide, and `rasterdraw.stroke_path`
  as one pixel wide after the transform.
- `rasterstroke.stroke_contains` builds the outline and tests it, so dashes, caps
  and joins are the drawn ones.
- A dash pattern with a negative entry, a NaN or an infinity is refused with
  `RstBadDash`, and so is a pattern that would cut a path into more than 4194304
  pieces. A pattern of odd length is used twice over. The pattern starts again at
  every subpath.
- A gradient without stops draws nothing, and `rasterpaint.color_at` answers
  transparent for it.
- `rasterpaint.transformed` moves a radial gradient's radius by the square root of
  the area scale of the matrix. It is exact for a rotation, a shift, a uniform
  scale and a mirror.
- `rasterdraw.clear` to a colour with no alpha keeps the colour it was given.
- `rasterglyph` draws a cached glyph at the left edge of its subpixel column, so a
  pen on a whole pixel is exact. `draw_run` keys a glyph on the scale's horizontal
  factor in 65536ths and draws the glyphs that have an outline when a run has more
  glyphs than outlines.

### Added

- `rasterpaint.blend_packed`, one blend of two pixels held as integers, with a
  coverage.
- `rasterpaint.ramp_position` and `rasterpaint.ramp_packed`, the position of a
  point on a paint's ramp and the ramp as a table of packed colours.
- `tests/oracle` holds the scripts that compare fills, strokes, gradients, blend
  modes, Oklab ramps and glyph masks with cairo, FreeType and published formulas,
  and `tests/coverage.sh` measures the merged line coverage over `src/`.

### Changed

- The dependency ranges move to `image-nv ^0.1.0` and `font-nv ^0.1.0`, and the
  package asks for novo 0.20.2 or later, which font-nv asks for.
- `stability` is `experimental` and the release is no longer an interface release.

## 0.0.3 — 2026-09-28

The dependency ranges move to the dependencies' current releases.  A
pre-1.0 caret range admits only the release it names, so the old
ranges held this package on interface releases, and a program could
not take this package beside those packages' current releases.  No
signature in this package changed.

- geometry-nv: `^0.0.1` to `^0.1.0`.
- svg-nv: `^0.0.1` to `^0.1.0`.
- color-nv: `^0.0.1` to `^0.1.1`.
- image-nv: `^0.0.1` to `^0.0.3`.
- font-nv: `^0.0.1` to `^0.0.3`.

## 0.0.2 — 2026-09-16

README rewritten to the package README style guide
(docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-11

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `rastermask` — `RstMask` as coverage with its own rectangle,
  `RstLimits` crossing the interface before an allocation, the four
  combining operations, and the two-call 1-bit conversion.
- `rasterfill` — the scanline sweep, `fill` / `fill_all` / `fill_rect`
  / `fill_convex`, the flattening tolerance in pixels, and hit testing
  against the same winding the sweep accumulates.
- `rasterstroke` — `outline` and `dash` as path-to-path operations,
  joins, caps, the miter limit, and `fill_rule` as a value.
- `rasterpaint` — `RstPaint` as one enum, gradients over color-nv's
  stops and spaces, and eleven blend modes with CSS's names.
- `rasterdraw` — `composite` as the one loop, the four calls a renderer
  makes, `RstDrawOpts` instead of canvas state, and the two mask/image
  conversions.
- `rasterglyph` — `RstGlyphKey` on integers, a cache the caller holds,
  and `draw_run` over a font-nv shaped run.
- `rastererror` — six refusals, and `is_budget` separating the one a
  caller can raise.

### Known

- **`RstMask` is the load-bearing interface.** Coverage is a value and
  compositing is a separate step, which is what makes a glyph cache
  colour-independent, a clip anti-aliased for free, and a mask from
  outside this package compositable through the same loop.
- **Anti-aliasing is analytic**, and
  `rasterfill.exact_coverage_is_claimed` is the promise a test holds to
  the pixel that is exactly 128.
- **A stroke is a path**, so it can be inspected, dashed and re-stroked
  — and it has exactly one legal fill rule, published as a value.
- **The caller owns the image.** No canvas, no context, no state
  between calls; `RstDrawOpts` is what would have been canvas state.
- **A mask's size crosses the interface before anything is allocated**,
  because the numbers in a path come out of a file.
- **Gradients interpolate in Oklab by default**, with the space a
  field so a caller reproducing an existing picture can ask for sRGB by
  name.
- **No device claim, and e-paper does not earn a module** — two
  functions and a `raster-embedded-nv` row, argued in the README.
- **font-nv is a PATH dependency** while the two are developed
  together, which `novo pkg publish --dry-run` refuses as it should.
  It becomes `^0.0.1` once font-nv is on the registry.
- image-nv brings png-nv, qoi-nv and flate-nv into the closure. Named
  rather than discovered, and `mask_to_image` is what makes the cost
  useful: a test can write out what the rasteriser did.
- The scaffold's `src/raster.nv` was dropped for seven prefixed
  modules.
