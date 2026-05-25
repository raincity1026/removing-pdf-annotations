#!/usr/bin/env python3
"""Remove PDF annotations — both standard /Annots and flattened Adobe Fill & Sign.

Usage:
    remove_pdf_annotations.py INPUT.pdf [OUTPUT.pdf]
    remove_pdf_annotations.py INPUT_DIR/        (writes to INPUT_DIR/cleaned/)

Why two passes? See the SKILL.md alongside this script. TL;DR: PDF annotations
can be either (a) annotation objects in the page's /Annots array — what every
"remove annotations" tool handles — or (b) drawing operations baked directly
into the page content stream by tools like Adobe Fill & Sign. The second kind
is invisible to standard tools. This script handles both.

Requirements: pypdf>=4 (pip install pypdf).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ContentStream, NameObject
except ImportError:
    sys.exit("pypdf is required. Install with: pip install pypdf")


# ── Fill & Sign content-stream surgery ────────────────────────────────────────

# BMC and BDC both open a marked-content section; EMC closes one. They are
# whole-word PDF operators and (per the spec, ISO 32000-1 §14.6) cannot appear
# inside string literals — so word-boundary regex is safe here.
OPEN_MARK = re.compile(rb"\b(BMC|BDC)\b")
CLOSE_MARK = re.compile(rb"\bEMC\b")
FILLSIGN_START = re.compile(rb"/ADBE_FillSign\s+BMC\b")


def _strip_fillsign(data: bytes) -> tuple[bytes, int]:
    """Remove every /ADBE_FillSign BMC ... EMC block, handling nesting.

    Returns (new_bytes, num_blocks_removed).
    """
    out = bytearray()
    i = 0
    removed = 0
    while True:
        m = FILLSIGN_START.search(data, i)
        if not m:
            out.extend(data[i:])
            return bytes(out), removed
        out.extend(data[i : m.start()])

        # Walk forward tracking nesting depth. Any BMC/BDC opens a level;
        # each EMC closes one. The skill's content stream surgery hinges on
        # getting this right — naively stopping at the first EMC truncates
        # the block when annotations contain inner marked content.
        depth = 1
        j = m.end()
        while depth > 0:
            o = OPEN_MARK.search(data, j)
            c = CLOSE_MARK.search(data, j)
            if c is None:
                # Malformed stream — bail without truncating.
                out.extend(data[m.start() :])
                return bytes(out), removed
            if o is not None and o.start() < c.start():
                depth += 1
                j = o.end()
            else:
                depth -= 1
                j = c.end()

        # Eat one trailing newline so we don't leave a blank line behind.
        if j < len(data) and data[j : j + 1] in (b"\n", b"\r"):
            j += 1
            if j < len(data) and data[j - 1 : j] == b"\r" and data[j : j + 1] == b"\n":
                j += 1
        i = j
        removed += 1


# ── Per-PDF cleaning ──────────────────────────────────────────────────────────


def clean_pdf(src: Path, dst: Path) -> tuple[int, int]:
    """Returns (n_annots_cleared, n_fillsign_blocks_removed)."""
    reader = PdfReader(str(src))
    writer = PdfWriter(clone_from=reader)

    annots_cleared = 0
    fillsign_removed = 0

    for page in writer.pages:
        if "/Annots" in page:
            annots_cleared += len(page["/Annots"])
            page[NameObject("/Annots")] = ArrayObject()

        contents = page.get_contents()
        if contents is None:
            continue
        try:
            raw = contents.get_data()
        except Exception as exc:
            print(f"  warn: skipping page (decode failed: {exc})", file=sys.stderr)
            continue

        new_raw, removed = _strip_fillsign(raw)
        if removed:
            fillsign_removed += removed
            stream = ContentStream(None, writer)
            stream.set_data(new_raw)
            page[NameObject("/Contents")] = writer._add_object(stream)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        writer.write(f)
    return annots_cleared, fillsign_removed


# ── CLI ───────────────────────────────────────────────────────────────────────


def _process(src: Path, dst: Path) -> None:
    annots, fs = clean_pdf(src, dst)
    print(f"  cleared {annots} /Annots, removed {fs} Fill&Sign block(s) → {dst}")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    src = Path(argv[0])
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 1

    if src.is_dir():
        out_dir = Path(argv[1]) if len(argv) > 1 else src / "cleaned"
        pdfs = sorted(src.glob("*.pdf"))
        if not pdfs:
            print(f"no PDFs in {src}", file=sys.stderr)
            return 1
        print(f"found {len(pdfs)} PDF(s)")
        for pdf in pdfs:
            print(pdf.name)
            try:
                _process(pdf, out_dir / pdf.name)
            except Exception as exc:
                print(f"  failed: {exc}", file=sys.stderr)
        return 0

    dst = Path(argv[1]) if len(argv) > 1 else src.with_name(src.stem + ".cleaned.pdf")
    print(src.name)
    _process(src, dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
