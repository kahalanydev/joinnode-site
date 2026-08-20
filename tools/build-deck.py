#!/usr/bin/env python3
"""Render the seed deck into the assets /investor-deck serves.

    python tools/build-deck.py "path/to/Node Deck.pdf"

Writes deck/NodeAI-Seed-Deck.pdf (the download), deck/slide-NN.webp (2x, the
viewer) and deck/thumb-NN.webp (the rail and grid). Requires PyMuPDF.

READ THIS BEFORE SHIPPING A NEW DECK VERSION
--------------------------------------------
Every published asset here is *derived*, not a copy. Several passes run over the
source PDF before anything is rendered, so the download and the slides agree:

  FORBIDDEN   Client brand names that must never reach a public asset. Checked
              on every build; a hit stops it. This is the backstop and it is
              always on, even when every other table is empty.
  REDACTIONS  Names to rewrite rather than merely refuse.
  CORRECTIONS Facts that are wrong in the deck itself and would mislead a reader.
  DELETIONS   Sentences pointing at something the deck no longer contains.
  LISTS       Lists that outlived some of their entries.

REDACTIONS and CORRECTIONS are empty as of deck v2, which cut the slide carrying
the client name and fixed the contact address at source. The machinery stays
because the next export can reintroduce either. DELETIONS and LISTS are in use:
v2 cut appendices A4 and A7 without updating the appendix contents slide or the
line on slide 10 that pointed at A4.

None of this shows in a diff: the repo holds only binaries. Drop a fresh export
in by hand and whatever the passes were catching goes straight back up on a
public URL with nothing to stop it. So always regenerate through this script,
and extend the tables when a new version needs it.

Every pass fails loudly rather than publish. An entry that matches nothing is an
error — the wording moved, or the slide was cut, and either way somebody should
look at it — and so is one that survives its own pass. Everything is checked
before a single byte is written, so a failed run leaves the shipped assets
alone.

Eyeball the rendered slide afterwards regardless. A redaction is redrawn in
Helvetica at the source size — close to the deck's Arial, not identical — and a
much longer replacement could collide with the next column. A correction is set
on the line's own letter pitch, so its tracking matches, but it has to fit
inside the footprint of the string it replaces.
"""

import os
import sys

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "deck")

# The client brands whose private order books feed the demand model. None of
# them may appear on a public asset, ever. This list is checked on every build
# and a hit STOPS it — it is the backstop, not the fixer. If one shows up,
# either get a clean export or add a REDACTIONS entry and eyeball the result.
FORBIDDEN = ["Laundry Sauce", "Relaxium", "Hairmax", "Caddis"]

# Confidential names to replace rather than merely refuse, and what the public
# asset says instead. Keep the replacement close to the original's width — see
# the module docstring. Empty since v2 of the deck: the only name was in the
# metro-math appendix, and that slide was cut.
REDACTIONS = {
    # "Laundry Sauce": "Subscription CPG brand",   # v1, slide A7
}

# Wrong in the source deck and misleading to a reader. Unlike a redaction these
# are the deck's own claims, so keep the list short and factual, and tell Elor
# what was changed rather than quietly fixing his slides. Empty since v2, which
# corrected the contact address at source.
CORRECTIONS = [
    # v1 slide 13 read ELOR.KAHALANY@NODEAI.COM, a domain we do not hold:
    # {"find": "ELOR.KAHALANY@NODEAI.COM", "replace": "ELOR@JOINNODE.AI", "why": ...},
]

# Sentences left pointing at something the deck no longer contains. Cleared, not
# rewritten — a dead pointer should go away, not be replaced with a new claim.
DELETIONS = [
    {
        "find": "Early capture rates are in the appendix.",
        "why": "those were the 8-30% / 40-66% figures on A4, and A4 was cut in v2",
    },
]

# Lists that outlived some of their entries. Give the whole list as it stands and
# as it should read; the surviving items are re-placed into the leading slots so
# no hole is left where a cut one was.
LISTS = [
    {
        "page": 14,
        "was": ["A1 · COMPETITIVE DETAIL", "A2 · UNIT ECONOMICS ASSUMPTIONS",
                "A3 · HOST ECONOMICS", "A4 · ADOPTION DETAIL",
                "A5 · EXPANSION MODEL", "A6 · FUTURE OPTIONALITY",
                "A7 · METRO MATH"],
        "now": ["A1 · COMPETITIVE DETAIL", "A2 · UNIT ECONOMICS ASSUMPTIONS",
                "A3 · HOST ECONOMICS", "A5 · EXPANSION MODEL",
                "A6 · FUTURE OPTIONALITY"],
        "why": "the appendix contents still promised A4 and A7 after v2 cut them",
    },
]

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


def forbid(doc):
    """Refuse to build if a client brand name is anywhere in the deck.

    Matches against the de-spaced text, because the deck's exports bake letter
    tracking in as real space characters — v2 writes even its section labels as
    'T H E  P R O B L E M'. A plain search would sail straight past a name set
    that way, which is exactly the failure this list exists to prevent.
    """
    for page in doc:
        flat = "".join(despace(page))
        for name in FORBIDDEN:
            if name.replace(" ", "") in flat.replace(" ", ""):
                raise SystemExit(
                    "%r is on page %d. Client brand names never go on a public "
                    "asset. Get an export without it, or add it to REDACTIONS "
                    "with a generic replacement and check the rendered slide."
                    % (name, page.number + 1))


def despace(page):
    """Every non-space glyph on the page, in reading order."""
    return [c["c"] for b in page.get_text("rawdict")["blocks"]
            for l in b.get("lines", []) for s in l["spans"]
            for c in s["chars"] if not c["c"].isspace()]


def glyphs(span):
    """The span's characters with the spaces the tracking baked in stripped out.

    The deck sets these labels in letter-spaced Courier, and the export writes
    that as literal spaces between glyphs at hand-placed positions — so the span
    reads 'EL O R . K A HA L A N Y@ N OD E A I . C OM' and no plain search finds
    the address. Dropping the spaces gives back the real string, and each
    surviving glyph keeps the x it was drawn at.
    """
    return [c for c in span["chars"] if not c["c"].isspace()]


def correct(doc):
    """Fix wrong facts in place, reusing the deck's own glyph grid."""
    changed = []
    for fix in CORRECTIONS:
        find, replacement = fix["find"], fix["replace"]
        hits = 0
        for page in doc:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        chars = glyphs(span)
                        at = "".join(c["c"] for c in chars).find(find)
                        if at < 0:
                            continue
                        hits += 1
                        run = chars[at:at + len(find)]
                        x0, y0, _, y1 = span["bbox"]
                        left, base = run[0]["origin"]
                        step = pitch(chars)

                        # Only the old string's footprint gets cleared, so the
                        # new one has to live inside it — past that edge it would
                        # overprint whatever sits further along the line.
                        end = left + (len(replacement) - 1) * step + span["size"] * 0.6
                        if end > span["bbox"][2]:
                            raise SystemExit(
                                "%r runs %.0fpt past the end of the line it replaces "
                                "on page %d — shorten it, or widen the cleared area "
                                "after checking what else is on that row."
                                % (replacement, end - span["bbox"][2], page.number + 1))

                        # Clear from the first glyph of the old string to the end
                        # of the span, then set the replacement on the line's own
                        # pitch. Reusing the old glyphs' exact x values instead
                        # would inherit that string's kerning quirks, and the new
                        # address came out visibly tighter than the label next to
                        # it — the run is monospaced, so an even step is right.
                        page.add_redact_annot(
                            fitz.Rect(left - 1, y0 - 2, span["bbox"][2] + 2, y1 + 2),
                            fill=page_bg(page, x0, y0, y1))
                        page.apply_redactions()

                        colour = rgb(span["color"])
                        for i, ch in enumerate(replacement):
                            page.insert_text((left + i * step, base), ch,
                                             fontname="cour", fontsize=span["size"],
                                             color=colour)
                        changed.append("p%d  %s -> %s  (%s)"
                                       % (page.number + 1, find, replacement, fix["why"]))
        if not hits:
            raise SystemExit(
                "%r matched nothing. Either the deck already says the right thing "
                "— drop the entry — or the text moved and the fix silently did not "
                "run." % find)

    for page in doc:
        for fix in CORRECTIONS:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if fix["find"] in "".join(c["c"] for c in glyphs(span)):
                            raise SystemExit("%r survived on page %d"
                                             % (fix["find"], page.number + 1))
    return changed


def pitch(chars):
    """The span's letter-to-letter step, as the most common gap between glyphs.

    These labels are monospaced with tracking, so nearly every in-word gap is
    the same number and the mode finds it. Gaps at word boundaries are wider but
    far rarer, and the odd kerned pair rarer still, so neither wins the vote.
    """
    gaps = [round(b["origin"][0] - a["origin"][0], 3)
            for a, b in zip(chars, chars[1:]) if b["origin"][0] > a["origin"][0]]
    if not gaps:
        raise SystemExit("cannot read a letter pitch from this span")
    return max(set(gaps), key=gaps.count)


def find_span(page, text):
    """The span whose whole text is `text`, ignoring baked-in letter spacing."""
    want = text.replace(" ", "")
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if "".join(c["c"] for c in span["chars"]).replace(" ", "") == want:
                    return span
    return None


def rule_above(page, span):
    """The hairline divider drawn over this list item, if the slide rules them."""
    x0, top = span["bbox"][0], span["bbox"][1]
    best = None
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.height < 3 and r.x0 <= x0 and r.x1 > x0 and 0 < top - r.y1 < 30:
            if best is None or r.y1 > best.y1:
                best = r
    return best


def delete(doc):
    """Clear dead sentences. Nothing is drawn back."""
    changed = []
    for cut in DELETIONS:
        find = cut["find"]
        hits = 0
        for page in doc:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        chars = glyphs(span)
                        at = "".join(c["c"] for c in chars).replace(" ", "").find(
                            find.replace(" ", ""))
                        if at < 0:
                            continue
                        hits += 1
                        # `at` indexes the space-stripped string; walk the glyphs
                        # to the same point so the x is the one actually drawn.
                        run = chars[at:at + len(find.replace(" ", ""))]
                        _, y0, _, y1 = span["bbox"]
                        page.add_redact_annot(
                            fitz.Rect(run[0]["origin"][0] - 2, y0 - 2,
                                      run[-1]["bbox"][2] + 2, y1 + 2),
                            fill=page_bg(page, run[0]["origin"][0], y0, y1))
                        page.apply_redactions()
                        changed.append("p%d  %s  (%s)"
                                       % (page.number + 1, find, cut["why"]))
        if not hits:
            raise SystemExit(
                "%r matched nothing. Either the deck already dropped it — remove "
                "the entry — or the wording moved and nothing was cut." % find)
    return changed


def reflow(doc):
    """Re-place a list's survivors into its leading slots."""
    changed = []
    for job in LISTS:
        page = doc[job["page"] - 1]
        spans = []
        for text in job["was"]:
            span = find_span(page, text)
            if span is None:
                raise SystemExit(
                    "%r is not on page %d. Give LISTS the whole list exactly as "
                    "the deck now has it — if the slide already dropped it, drop "
                    "it here too." % (text, job["page"]))
            spans.append(span)

        missing = [t for t in job["now"] if t not in job["was"]]
        if missing:
            raise SystemExit("LISTS 'now' may only keep items from 'was': %s" % missing)

        # Slots in reading order, and one pitch for the lot — they are all the
        # same tracked monospace, so an item keeps its width wherever it lands.
        slots = sorted((round(s["bbox"][1], 1), s["chars"][0]["origin"][0], s)
                       for s in spans)
        steps = [pitch(glyphs(s)) for s in spans]
        step = max(set(steps), key=steps.count)
        columns = sorted({x for _, x, _ in slots})

        for text, (_, x, span) in zip(job["now"], slots):
            right = next((c for c in columns if c > x), page.rect.width - 60)
            end = x + (len(text) - 1) * step + span["size"] * 0.6
            if end > right:
                raise SystemExit(
                    "%r would run %.0fpt into the next column on page %d"
                    % (text, end - right, job["page"]))

        # Slots that keep an item are cleared down to the text only, so the rule
        # ruled above them survives. Slots that fall empty take their rule with
        # them — a divider with nothing under it is worse than the stale entry.
        for i, (_, _, span) in enumerate(slots):
            x0, y0, x1, y1 = span["bbox"]
            box = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
            if i >= len(job["now"]):
                divider = rule_above(page, span)
                if divider is not None:
                    box |= fitz.Rect(divider.x0 - 1, divider.y0 - 1,
                                     divider.x1 + 1, divider.y1 + 1)
            page.add_redact_annot(box, fill=page_bg(page, x0, y0, y1))
        page.apply_redactions()

        for text, (_, x, span) in zip(job["now"], slots):
            base = span["chars"][0]["origin"][1]
            colour = rgb(span["color"])
            for i, ch in enumerate(text):
                if ch != " ":
                    page.insert_text((x + i * step, base), ch, fontname="cobo",
                                     fontsize=span["size"], color=colour)

        dropped = [t for t in job["was"] if t not in job["now"]]
        changed.append("p%d  dropped %s  (%s)"
                       % (job["page"], ", ".join(dropped), job["why"]))
    return changed


def rgb(packed):
    return ((packed >> 16 & 255) / 255, (packed >> 8 & 255) / 255, (packed & 255) / 255)


def page_bg(page, x, y0, y1):
    """The page colour just left of x on that row, so a patch cannot show."""
    pix = page.get_pixmap(dpi=72, clip=fitz.Rect(max(0, x - 8), y0, max(1, x - 2), y1))
    return tuple(v / 255 for v in pix.pixel(0, pix.height // 2))


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
    forbid(doc)
    for line in redact(doc):
        print("redacted   " + line)
    for line in correct(doc):
        print("corrected  " + line)
    for line in delete(doc):
        print("deleted    " + line)
    for line in reflow(doc):
        print("reflowed   " + line)

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
