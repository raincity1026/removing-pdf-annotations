# removing-pdf-annotations

A Claude Code skill (and standalone script) for removing PDF annotations that
**survive** the usual "remove annotations" tools — the colored handwriting,
highlights, and scribbles added by Adobe Fill & Sign, the Acrobat mobile app,
and similar tools that flatten drawings into the page content stream.

## The Problem

PDF annotations come in two flavors:

1. **Annotation objects** in each page's `/Annots` array. Sticky notes,
   highlights with a `/Subtype`, freehand drawings stored as `/Ink`. These
   clear cleanly with pypdf / qpdf / Acrobat's "Remove All Comments".
2. **Flattened drawing operations** baked into the page content stream. After
   flattening there is no annotation object — the marks are just `lines` and
   `curves` and `images` in the page itself, indistinguishable from the
   original print. Standard tools have nothing to remove.

If you've ever cleared `/Annots` on a PDF and watched the file save with the
red ink still all over it, you've hit kind #2.

## The Fix

Adobe Fill & Sign — by far the most common source of this problem on
school/exam PDFs and signed forms — leaves a `/ADBE_FillSign BMC ... EMC`
marked-content block around its drawings. The script in this repo:

1. Clears the `/Annots` array on every page (standard pass).
2. Walks each page's content stream and removes every `/ADBE_FillSign` block,
   correctly handling nested marked-content sections.
3. Saves the result with the text layer and original content intact.

No rasterization, no OCR, no loss of searchability.

## Quick Start (Standalone Script)

```bash
pip install pypdf
python scripts/remove_pdf_annotations.py INPUT.pdf OUTPUT.pdf

# Or process a whole directory:
python scripts/remove_pdf_annotations.py path/to/pdfs/
# writes cleaned copies to path/to/pdfs/cleaned/
```

## Install as a Claude Code Skill

Skills live under `~/.claude/skills/`. Drop this whole repo there:

```bash
git clone https://github.com/<YOUR-USERNAME>/removing-pdf-annotations.git \
    ~/.claude/skills/removing-pdf-annotations
```

Next time you ask Claude Code to remove PDF annotations and the usual approach
fails, it will find this skill via the description and apply the right
technique automatically.

## When This Won't Work

The skill targets `/ADBE_FillSign` markers specifically. Annotations flattened
by other tools (Preview's "export with annotations", GoodNotes, Notability)
don't leave that marker. See the **"When this skill doesn't help"** section in
[SKILL.md](SKILL.md) for fallback options (other marked-content tags, Form
XObject removal, rasterize-and-clean).

**This is not a redaction tool.** It removes visible drawings, but the
original content stream history may still be recoverable via PDF forensics.
Do not use this to redact confidential information.

## Contributing

PRs welcome, especially:

- Markers from other tools (Foxit, Xodo, Kami, etc.) that flatten with a
  distinguishable signature.
- Detection helpers — "what type of annotation flattening is this?"
- Test fixtures (small, non-sensitive PDFs).

## License

MIT — see [LICENSE](LICENSE).
