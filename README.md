# raster-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

A software rasteriser: paths in, an anti-aliased **coverage mask** out,
and compositing as a separate step. The backend plot-nv declared, the
glyph renderer novoterm needs, and the fill behind svg-nv's paths.

- `rastermask` — `RstMask`, coverage as a value; the load-bearing type;
- `rasterfill` — the scanline sweep with analytic anti-aliasing;
- `rasterstroke` — strokes and dashes, path-to-path;
- `rasterpaint` — solid, linear, radial and sweep paints; blend modes;
- `rasterdraw` — compositing into an image-nv `Image` the caller owns;
- `rasterglyph` — font-nv outlines, with a cache the caller holds;
- `rastererror` — the six things a rasteriser refuses.

```
novo pkg add raster-nv
novo pkg build
novo test
```

## The one example that will work

Drawing a plot's bar and its label into an image the caller allocated.

```novo ignore
use rasterdraw
use rasterpaint
use rasterstroke
use rasterglyph

fn draw_bar(img: Image, bar: SvgPath, label: FontShaped, outlines: [SvgPath],
            cache: RstGlyphCache, scale: GeomXform) -> Result<(Image, RstGlyphCache), RstFault>
    let o = rasterdraw.opts(img.width, img.height)

    // The fill, in one call, with the caller's image going in and
    // coming back.
    var out = rasterdraw.fill_path(img, bar, rasterpaint.solid(blue),
                                   GeomNonZero, GeomXform.identity(), o)!

    // The outline of the same bar, at a hairline.
    out = rasterdraw.stroke_path(out, bar, rasterpaint.solid(navy),
                                 rasterstroke.solid(1.0), GeomXform.identity(), o)!

    // And the label, through the glyph cache, in one pass over the run.
    rasterglyph.draw_run(out, cache, label, outlines, scale, 0,
                         12.0, 40.0, rasterpaint.solid(black), o)
```

## The load-bearing interface: `RstMask`

```novo ignore
pub struct RstMask
    width: Int
    height: Int
    origin_x: Int
    origin_y: Int
    coverage: Bytes
```

**A rasteriser's real output is not pixels.** It is the answer to one
question per pixel — how much of this pixel does the shape cover? — and
that answer is a number between 0 and 255 that knows nothing about what
colour the shape is. Making that number a published value, and
compositing a separate step that consumes one, is the decision the rest
of this package follows from.

**A glyph cache holds masks, not pixels.** A terminal draws the same
`e` in sixteen colours; an editor draws it selected and unselected; a
plot draws its labels grey and its title black. A cache of pixels holds
one entry per (glyph, size, colour) and rasterises the same outline
again for every colour. A cache of coverage holds one entry per (glyph,
size, subpixel column), and the colour arrives at the blend.

**A clip is the same value.** Clipping to a shape is
`rastermask.intersect` of two masks, so a clip is anti-aliased for free
and a clip to a rotated rectangle is not a special case. tiny-skia
keeps a `ClipMask` separate from its pixmap for the same reason; having
one type for both halves is the simplification.

**A mask can be produced by something that is not this package.** A
decoded PNG's alpha channel, a blur, a mask from last frame —
`rasterdraw.composite` is public, so any of them composites through the
same loop. That is the practical payoff, and it is why `composite` is
not an internal detail of `fill_path`.

**And the 1-bit case is a threshold**, not a second rasteriser. See
below.

The mask carries its own rectangle, which is the field that makes it
usable: a path's coverage is zero almost everywhere, so a mask covers
the path's bounding box clipped to the target and `origin_x`/`origin_y`
say where that box sits. Eight bits and not sixteen, because a byte is
what a composite against an 8-bit image can use without rounding twice,
it is what every font atlas in the world stores, and it makes a
1024-square mask one megabyte rather than four.

## Three decisions worth arguing

### Analytic anti-aliasing, and a test that can hold it to that

There are two ways to anti-alias a filled path. Supersampling asks "is
the shape here?" at sixteen points in the pixel and counts the yeses:
sixteen times the work, and coverage quantised to seventeen levels —
visible as banding on a shallow edge, which is most of a letterform.
The analytic method integrates the exact area the edges cut out of each
pixel: one pass, exact answers.

The difference is a number a test can assert. A 45-degree edge through
the centre of a pixel covers exactly half of it, and this rasteriser
says **128** — not "about 128".
`rasterfill.exact_coverage_is_claimed()` is that promise as a function
so the test suite can assert the claim beside the pixel that
demonstrates it.

### A stroke is a path, not a drawing operation

`rasterstroke.outline` answers an `SvgPath`. Three things follow.

The stroke can be **inspected** — measured, hit-tested, written to an
SVG file, stroked again. Dashing **composes**, because
`rasterstroke.dash` is also path-to-path and the two chain in the order
the specification says: dash first, then stroke. And the fill rule is
**not a choice**: a stroke outline's two offsets run in opposite
directions, so an even-odd fill hollows out every overlap — and an
overlap is what a join *is*. `rasterstroke.fill_rule()` says
`GeomNonZero` as a value, so nobody has to remember.

The zero-width case gets a name rather than a silent pick. SVG says a
width of 0 draws nothing; PostScript and most plotting libraries say
one device pixel. Both are defensible, and a library that quietly chose
is a library whose output changes when you switch to it. So width 0
draws nothing, matching SVG, and `rasterstroke.hairline()` is the call
that asks for the other reading.

### No canvas, and the caller owns the pixels

Every call in `rasterdraw` takes an `Image` and answers an `Image`.
There is no surface, no context, no state carried between calls. The
package cannot leak a buffer because it never holds one; a draw is
testable at the value level with no setup; and double buffering belongs
to the caller, which is right, because a terminal, a plot and a static
site want three different answers about when a frame is finished.

What would have been canvas state is `RstDrawOpts` — clip, blend mode,
paint transform — passed in. A clip set three statements ago is not
something a reader has to reconstruct.

## What plot-nv's `plotraster` would call

plot-nv's `render` is a pure function to a list of twelve draw
operations, and each target replays them. `plotraster` is the replay
for this package, and the whole of it is a `match` whose arms are four
calls:

| plot-nv operation | the call |
| --- | --- |
| a filled bar, a wedge, an area | `rasterdraw.fill_path(img, path, rasterpaint.solid(c), GeomNonZero, xform, o)` |
| a data series, an error bar | `rasterdraw.stroke_path(img, path, rasterpaint.solid(c), rasterstroke.solid(w), xform, o)` |
| a gridline, a background panel | `rasterdraw.fill_rect(img, rect, rasterpaint.solid(c), o)` |
| an axis label, a title, a legend entry | `rasterglyph.draw_run(img, cache, run, outlines, scale, font_id, x, y, rasterpaint.solid(c), o)` |

with `o = rasterdraw.opts_at(clip)` and the image threaded through. No
fifth kind of operation, and no state between them — which is what
makes a replay a fold rather than a driver.

A dashed gridline is `rasterstroke.dash` before the stroke; a gradient
fill swaps `rasterpaint.solid` for `rasterpaint.linear` and changes
nothing else. That is the argument for the paint being an enum rather
than three drawing calls.

## Does e-paper earn a module?

**No — it earns two functions, and a row of its own.**

`rastermask.threshold` turns coverage into 0 or 255, and
`rastermask.pack_rows_1bit` packs the result eight pixels to a byte,
most significant bit leftmost, which is what every monochrome panel
controller and every 1-bit BMP expects. That is the whole conversion,
and packing is published rather than left to the caller because the bit
*order* is the thing you get wrong once and then cannot see is wrong —
a picture packed the other way looks like static.

What a module would have to be is a *different algorithm*, and that is
the argument against putting it here. The expensive part of this
rasteriser is the edge list, the sort and the active-edge walk, and a
1-bit output makes none of it cheaper; the mask is still a byte per
pixel while it is being built. A device with 4 KB of RAM cannot afford
either. What it actually needs is a span filler over a fixed
scanline buffer with integer coordinates and no edge list at all —
which is a different package, not a module, because it shares no code
with this one and would drag `@tier(embedded)` constraints across
every type here.

So: **`raster-embedded-nv` is a row the grid does not yet have**, and
this package makes **no `@tier(embedded)` claim**. `docs/publishing.md`
says a device claim is built and not asserted; there is no device
consumer for a general rasteriser today, and a claim nobody needs is a
claim nobody maintains.

## What this does not do, by name

| | |
| --- | --- |
| **Resampling** | Scaling and rotating an image is image-nv's `imageops`. `rasterdraw.draw_image` is nearest-neighbour at integer offsets only, because a second, worse answer to a question that already has one is worse than no answer. |
| **Blur, shadows and filters** | An SVG filter chain is its own subject and its own row. |
| **The two-circle radial gradient** | SVG allows a focal point inside a larger circle. It needs a different parameter solve, it is rare, and approximating it with a concentric gradient is a visible difference a caller cannot see coming — so it is absent rather than wrong. |
| **16-bit destinations** | `rasterdraw.kinds_supported` names the four it composites into. An 8-bit mask against a 16-bit image rounds coverage twice, and a caller working at 16 bits chose that precision for a reason. |
| **Hinting and stem darkening** | Hinting is font-nv's absent TrueType instruction interpreter. Stem darkening is a gamma decision about the caller's whole pipeline, and `rastermask.scale` is where a caller that wants it applies it. |
| **Subpixel (LCD) anti-aliasing** | Three coverage values per pixel instead of one, and a filter to stop the colour fringing. It changes `RstMask`'s shape, so it is a decision for the implementation step and is named here rather than assumed. |
| **Self-intersection removal in strokes** | A tight curve's offset crosses itself. The non-zero fill makes the result look right, which is what every 2D library does; genuinely removing them is one of the hard problems in the field. |
| **Threads** | Single-threaded by construction. A `core` package has no way to start one, and tiling is the caller's — which `rasterdraw.opts_at` is there for. |

## Dependencies

| | |
| --- | --- |
| `geometry-nv ^0.0.1` | `GeomXform`, `GeomRectF`, `GeomRectI`, `GeomPoly`, and **`GeomFillRule`**. The fill rule is the load-bearing reuse: even-odd and non-zero are the same two rules SVG names, svg-nv already passes the value straight through, and a `RstFillRule` here would mean converting between two enums with the same two variants — with `E2004` waiting for the program that ends up with both. |
| `svg-nv ^0.0.1` | `SvgPath` and `SvgPathCmd`: the one typed path on the grid, and what font-nv's outlines already are. |
| `color-nv ^0.0.1` | `Srgb8`, `Srgba8`, `ColorStop`, `ColorSpace`. The gradient stop list *is* `[ColorStop]` and the interpolation space *is* `ColorSpace`, which is what makes an Oklab gradient one argument rather than a second gradient type. |
| `image-nv ^0.0.1` | `Image` and `PixelKind`: the buffer the caller owns. It brings png-nv, qoi-nv and flate-nv with it, because image-nv is the multi-format front — a cost worth naming, and the reason `rasterdraw.mask_to_image` exists: it is what lets a test write out what the rasteriser did. |
| `font-nv` **by path** | `rasterglyph` alone. See below. |

### The path dependency, and what the publish said

`font-nv` is declared `{ path = "../font-nv" }` while the two are
developed together, and **`novo pkg publish --dry-run` refuses it**, at
the line the entry is written on:

```
novo.toml: error: dependency 'font-nv' is declared by the path "../font-nv",
and a published package depends only on published packages
```

That refusal is right, and `docs/publishing.md` § Dependencies between
published packages says why: the tarball would carry `../font-nv` and
send every consumer to a directory that is not on their machine. The
line becomes `font-nv = "^0.0.1"` once font-nv is on the registry, and
font-nv is published first because a package cannot be published ahead
of what it depends on. The lane recorded the refusal and then ran the
dry-run again over a scratch copy with the range in place, which is
accepted as an interface release.

`rasterglyph` is the only module that names font-nv: `SvgPath` in font
units, `GeomXform` from `fontmetric.scale_for_px`, and `FontShaped`
for a whole run. Every other module is reachable without it.

## The layer, and why

`core`. A rasteriser is arithmetic over numbers the caller already
holds: an edge list, a sort, a coverage accumulation, a blend. Nothing
is opened, nothing is written, no clock is read, and every output
buffer belongs to the caller.

There is no `FontSource`-shaped seam here and none is needed: this
package is handed outlines, and reading them is font-nv's business.

## The reference implementation

`tiny-skia` (BSD-3-Clause), which is Skia's raster pipeline ported to
Rust without the C++ — the same job this package has, and the source of
the `ClipMask`-separate-from-pixmap shape. Pillow's `ImageDraw` for the
surface a caller reaches for first. Skia's own behaviour is the
correctness reference where the two disagree.

## Status

| | |
| --- | --- |
| version | 0.0.1, `stability = "draft"` |
| modules | 7 |
| public functions | 91, every body a `todo()` |
| public types | 5 boxed structs, 3 `@value` structs, 6 enums with 30 variants |
| tests | 37, 195 assertions, red until bodies land |
| device claim | none, and § Does e-paper earn a module says why |
