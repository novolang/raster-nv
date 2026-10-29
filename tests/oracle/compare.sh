#!/usr/bin/env bash
# tests/oracle/compare.sh - fill, stroke, gradient and blend scenarios run
# through this package and through the oracle, and the planes compared.
#
# The oracles are FreeType (the area coverage of a fill, and of glyph
# outlines) and cairo with pixman (strokes, gradients and blend modes).
# They need libfreetype.so.6, python3 with numpy and cairo.  Run from the
# package directory:  bash tests/oracle/compare.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(cd "$HERE/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/raster-nv-oracle.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
( cd "$PKG" && novo build tests/oracle/probe.nv -o "$WORK/probe" >"$WORK/build.log" 2>&1 ) \
  || { cat "$WORK/build.log"; echo "probe did not build"; exit 1; }
python3 "$HERE/compare.py" "$WORK/probe" "$@"
