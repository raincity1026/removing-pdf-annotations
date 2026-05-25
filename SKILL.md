---
name: removing-pdf-annotations
description: Use when annotations remain visible in a PDF after running standard "remove annotations" tools (clearing /Annots with pypdf, qpdf, Acrobat "Remove Annotations"), especially colored handwriting/scribbles/highlights that look like they were added on a tablet or in Adobe Fill & Sign
---

# Removing PDF Annotations (Including Flattened Ones)

## Overview

PDF annotations live in **two different layers**. Standard tools only touch the first.

| Layer | Where it lives | How it's removed |
|---|---|---|
| **Annotation objects** | `/Annots` array on each `/Page` | Clear the array (pypdf, qpdf, Acrobat) |
| **Flattened content** | Baked into the page's `/Contents` stream as drawing ops | Edit the content stream itself |

When someone uses Adobe **Fill & Sign**, the iOS/Android Acrobat app, GoodNotes "flatten on export", or similar tools, the ink/text gets drawn into the page content stream and the annotation objects are dropped. To a normal tool the PDF looks un-annotated. To the eye, the markings are still all over the page.

**The good news:** Adobe Fill & Sign leaves a marker. Drawings are wrapped in a marked-content block:

```
/ADBE_FillSign BMC
    ... (drawing ops, may contain nested BMC/BDC) ...
EMC
```

Strip these blocks from each page's content stream and the visible annotations disappear — without re-rendering, without OCR, without losing the original text layer.

## When To Use

**Symptoms:**
- You ran `pypdf` `page["/Annots"] = ArrayObject()` and the PDF still looks annotated
- You ran `qpdf` (it has no `--remove-annotations`; that's another sign you're in this space)
- Acrobat → "Remove All Comments" did nothing visible
- The annotations look hand-drawn, colored, and follow a touch/pen path (not selection highlights)
- The PDF came from someone using an iPad, Surface, Adobe Fill & Sign, or "annotate and send"

**Not the right skill for:**
- Real annotation objects (sticky notes, text highlights with `/Subtype /Highlight`) — those clear normally with `/Annots = []`
- Annotations baked into a scanned/rasterized page (the whole page is one image) — need image processing, not content stream surgery
- Confidential redactions — this skill removes visible drawings but is **not** a security tool

## Diagnose First

Before reaching for any tool, confirm what kind of annotations you have:

```python
from pypdf import PdfReader
import re

r = PdfReader("input.pdf")
for i, p in enumerate(r.pages):
    n_annots = len(p.get("/Annots", []))
    c = p.get_contents()
    raw = c.get_data() if c is not None else b""
    n_fillsign = len(re.findall(rb"/ADBE_FillSign\s+BMC", raw))
    print(f"page {i}: /Annots={n_annots}  /ADBE_FillSign blocks={n_fillsign}")
```

| Output pattern | Diagnosis | Action |
|---|---|---|
| `/Annots>0`, `/ADBE_FillSign=0` | Standard annotations | Clear `/Annots`. Standard tools work. |
| `/Annots=0`, `/ADBE_FillSign>0` | Flattened Fill & Sign | Use this skill's script. |
| Both positive | Both layers present | Do both. |
| Both zero, but eye sees marks | Other flattening (image overlay, generic drawing ops) | See "When this skill doesn't help" below. |

## The Fix

`scripts/remove_pdf_annotations.py` handles both layers in one pass:

```bash
python remove_pdf_annotations.py INPUT.pdf OUTPUT.pdf
# or process a whole directory (writes to <dir>/cleaned/)
python remove_pdf_annotations.py INPUT_DIR/
```

What the script does, in order:

1. Clears every page's `/Annots` array.
2. Scans each `/Contents` stream for `/ADBE_FillSign BMC` and removes the block to its matching `EMC`, tracking nested BMC/BDC depth so it doesn't truncate at the first inner `EMC`.
3. Writes the result with `pypdf.PdfWriter`.

The matching loop is the part that's easy to get wrong — see "Common Mistakes" below.

## Common Mistakes

**1. Stopping at the first `EMC`.** Marked-content blocks nest. `BMC` and `BDC` both open a level; `EMC` closes one. If you naively remove `/ADBE_FillSign BMC ... EMC` with a non-greedy regex, you'll close at the first inner `EMC` and leave half the annotation drawing on the page.

**2. Trusting "annotations removed" without visual verification.** Open the output in Preview/Acrobat and look. The two-layer model means a tool can report "0 annotations remaining" while the page is still covered in ink.

**3. Reaching for OCR or rasterization first.** Both destroy the original text layer, fonts, and searchability. Try content stream surgery first — it's lossless when it works.

**4. Assuming all flattened annotations are Fill & Sign.** Other tools flatten too (Preview's "Export with annotations", GoodNotes, Notability). They don't leave the `/ADBE_FillSign` marker. See "When this skill doesn't help".

**5. Modifying the content stream as text.** PDF content streams can contain binary in inline images and string literals `(...)` / hex strings `<...>`. The technique works here because `BMC`/`BDC`/`EMC` are whole-word operators outside any string context — but if you extend the approach to other markers, watch out.

## When This Skill Doesn't Help

If `/ADBE_FillSign` markers aren't present but you still see annotations, the flattening was done differently. Options, roughly in order of preservation:

1. **Inspect for other marked-content tags.** Search the content stream for other `BMC`/`BDC` tags (`/Artifact`, vendor-specific names). Same removal technique applies.
2. **Find the annotation Form XObject by name.** Some tools draw annotations as a referenced Form XObject (`/Fm0 Do` in the content stream). If you can identify it (small bbox, only used in one place), you can replace the `Do` call with nothing.
3. **Rasterize and clean by color.** If original is black-and-white text and annotations are colored, render each page, threshold out non-grayscale pixels, rebuild PDF. Destroys text layer.
4. **OCR a clean rasterized version.** Last resort — full quality loss but produces a searchable result.

## Real-World Impact

The original use case: 10 Singapore primary-school science exam PDFs (~22 MB total) annotated by a parent in red pen via Adobe Fill & Sign. Standard `/Annots` clearing reported success but produced no visible change. The technique in this skill removed 84 marked-content blocks across the 10 files in under 2 seconds, with the original printed exam intact and searchable.
