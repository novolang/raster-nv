# Changelog

All notable changes to raster-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

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
