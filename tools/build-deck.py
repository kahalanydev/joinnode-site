#!/usr/bin/env python3
"""Render the seed deck into the assets /investor-deck serves.

    python tools/build-deck.py "path/to/Node Deck.pdf"

Writes deck/NodeAI-Seed-Deck.pdf (the download), deck/slide-NN.webp (2x, the
viewer) and deck/thumb-NN.webp (the rail and grid). Requires PyMuPDF.

READ THIS BEFORE SHIPPING A NEW DECK VERSION
--------------------------------------------
Client brand names must never appear on a public asset, and the deck names one
in the metro-math appendix. Every published asset here is therefore *derived*,
not a copy — the name is redacted out of the PDF before anything is rendered,
so the download and the slides agree.

That redaction is invisible in a diff: the repo only holds binaries. Re-export
the deck, drop the new PDF in by hand, and the name goes back up on a public
URL with nothing to catch it. So: always regenerate through this script, and
extend REDACTIONS if a later version names a different client.

It fails loudly rather than publishing a name — an entry that matches nothing is
an error (the wording changed, or the slide was cut), and so is a name that
survives the pass. Check the rendered slide afterwards regardless: replacement
text is drawn in Helvetica at the source size, which is close to the deck's
Arial but not identical, and a much longer name could collide with the next
column.
"""

import os
import sys

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "deck")

# Confidential client names, and what the public asset says instead. Keep the
# replacement close to the original's width — see the module docstring.
REDACTIONS = {
    "Laundry Sauce": "Subscription CPG brand",
}

# Sampled off the appendix page background and the body ink, so the patch is
# invisible. Both pages that could carry a client name share this treatment.
BG = (241 / 255, 240 / 255, 235 / 255)
INK = (0x47 / 255, 0x4C / 255, 0x54 / 255)


def redact(doc):
    """Replace confidential names in place. Returns a list of what it changed."""
    changed = []
    for name, replacement in REDACTIONS.items():
        found = False
        for page in doc:
            hits = page.search_for(name)
            if not hits:
                continue
            found = True
            for rect in hits:
                span = span_at(page, rect)
                if span is None:
                    raise SystemExit(
                        "%r found on page %d but its text span could not be read"
                        % (name, page.number + 1)
                    )
                size = span["size"]
                width = fitz.get_text_length(replacement, fontname="helv", fontsize=size)
                room = free_width(page, span)
                if width > room:
                    raise SystemExit(
                        "%r is %.0fpt wide but only %.0fpt is free before the next "
                        "column on page %d — shorten it"
                        % (replacement, width, room, page.number + 1)
                    )
                # Clear to just short of whatever comes next, so the redaction
                # cannot swallow the figure in the adjacent cell.
                page.add_redact_annot(
                    fitz.Rect(rect.x0 - 1, rect.y0 - 2, rect.x0 + room, rect.y1 + 2),
                    fill=BG,
                )
                page.apply_redactions()
                page.insert_text(span["origin"], replacement,
                                 fontname="helv", fontsize=size, color=INK)
                changed.append("p%d  %s -> %s" % (page.number + 1, name, replacement))
        if not found:
            raise SystemExit(
                "%r matched nothing. Either the deck no longer names it — drop the "
                "entry — or the wording moved and the redaction silently did not run."
                % name
            )

    for page in doc:
        for name in REDACTIONS:
            if page.search_for(name):
                raise SystemExit("%r survived the redaction on page %d"
                                 % (name, page.number + 1))
    return changed


def span_at(page, rect):
    """The text span whose bbox matches rect — for its font size and baseline."""
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if abs(span["bbox"][0] - rect.x0) < 1 and abs(span["bbox"][1] - rect.y0) < 1:
                    return span
    return None


def free_width(page, span):
    """Horizontal room from the span's start to the next text on its line."""
    x0, y0, _, y1 = span["bbox"]
    limit = page.rect.width
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for other in line["spans"]:
                ox0, oy0, _, oy1 = other["bbox"]
                overlaps = oy0 < y1 and oy1 > y0        # same visual row
                if overlaps and ox0 > x0 + 1:
                    limit = min(limit, ox0)
    return limit - x0 - 4                                # a little breathing room


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]

    doc = fitz.open(src)
    for line in redact(doc):
        print("redacted  " + line)

    os.makedirs(OUT, exist_ok=True)
    doc.save(os.path.join(OUT, "NodeAI-Seed-Deck.pdf"), garbage=4, deflate=True)

    stale = [f for f in os.listdir(OUT)
             if f.startswith(("slide-", "thumb-")) and f.endswith(".webp")]
    for f in stale:
        os.remove(os.path.join(OUT, f))          # a shorter deck must not keep old slides

    for i, page in enumerate(doc):
        n = i + 1
        page.get_pixmap(matrix=fitz.Matrix(2, 2)).pil_save(
            os.path.join(OUT, "slide-%02d.webp" % n), format="WEBP", quality=82, method=6)
        page.get_pixmap(matrix=fitz.Matrix(0.42, 0.42)).pil_save(
            os.path.join(OUT, "thumb-%02d.webp" % n), format="WEBP", quality=72, method=6)

    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print("wrote %d slides to deck/  (%.1f MB)" % (doc.page_count, total / 1024 / 1024))
    print("SLIDES in investor-deck.html lists a title per slide — update it if the "
          "deck gained, lost or reordered pages.")


if __name__ == "__main__":
    main()
