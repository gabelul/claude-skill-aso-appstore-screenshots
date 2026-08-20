"""
Headline typography — the single source of truth for how the text block is measured and drawn.

Both stages of the pipeline need identical text: `compose.py` draws it onto the scaffold,
and `restamp.py` draws it again on top of the AI-enhanced render. If those two ever
disagreed by a pixel the headline would visibly jump between stages, so the layout
constants and the drawing code live here and nowhere else.
"""

from PIL import Image, ImageDraw

from fonts import load_font

# ── Canvas ──────────────────────────────────────────────────────────
CANVAS_W = 1290
CANVAS_H = 2796

# ── Typography ──────────────────────────────────────────────────────
VERB_SIZE_MAX = 256
VERB_SIZE_MIN = 150
DESC_SIZE = 124
VERB_DESC_GAP = 20
DESC_LINE_GAP = 24
MAX_TEXT_W = int(CANVAS_W * 0.92)
MAX_VERB_W = int(CANVAS_W * 0.92)

TEXT_TOP = 200  # y of the first text baseline block


def word_wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_font(text, max_w, size_max, size_min):
    """Return the largest font size where text fits within max_w."""
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for size in range(size_max, size_min - 1, -4):
        font = load_font(size)
        bbox = dummy.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            return font
    return load_font(size_min)


def draw_centered(draw, y, text, font, max_w=None):
    lines = word_wrap(draw, text, font, max_w) if max_w else [text]
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        # anchor="mt" (middle-top) for pixel-perfect horizontal centering.
        # Subtract bbox[1] so the glyph top lands on the intended y.
        draw.text((CANVAS_W // 2, y - bbox[1]), line, fill="white", font=font, anchor="mt")
        y += h + DESC_LINE_GAP
    return y


def draw_headline(draw, verb, desc):
    """
    Draw the two-line headline at its canonical position.

    @param draw - ImageDraw target, must be a CANVAS_W-wide surface
    @param verb - Action verb, e.g. "TRACK" (uppercased here)
    @param desc - Benefit descriptor, e.g. "EVERY VACCINE RECORD"
    @returns y coordinate of the bottom of the drawn text block
    """
    verb_font = fit_font(verb.upper(), MAX_VERB_W, VERB_SIZE_MAX, VERB_SIZE_MIN)
    desc_font = load_font(DESC_SIZE)

    y = TEXT_TOP
    y = draw_centered(draw, y, verb.upper(), verb_font)
    y += VERB_DESC_GAP
    return draw_centered(draw, y, desc.upper(), desc_font, max_w=MAX_TEXT_W)


def headline_bottom(verb, desc):
    """Measure where the headline block ends without drawing it."""
    dummy = ImageDraw.Draw(Image.new("RGBA", (CANVAS_W, CANVAS_H)))
    verb_font = fit_font(verb.upper(), MAX_VERB_W, VERB_SIZE_MAX, VERB_SIZE_MIN)
    desc_font = load_font(DESC_SIZE)
    y = TEXT_TOP
    y = draw_centered(dummy, y, verb.upper(), verb_font)
    y += VERB_DESC_GAP
    return draw_centered(dummy, y, desc.upper(), desc_font, max_w=MAX_TEXT_W)
