#!/usr/bin/env python3
"""
Turn a raw enhanced render into an App Store Connect-ready screenshot.

Three jobs, in order: crop to Apple's aspect ratio, resize to exact pixel dimensions,
and repaint the headline.

That last one is the important one. The enhance pass is an image model, and image models
re-render text rather than preserving it — you get subtly wrong letterforms plus upscaling
ringing, on the single largest and most conversion-critical element of the screenshot. So we
let the model do the part only it can do (photoreal device, depth, breakout panels) and paint
the headline back on from `headline.py`, the same code that drew the scaffold. Pixel-identical
type on every screenshot in the set, for free.

Both backends land here, whatever aspect ratio they hand back, so the pipeline has one
post-processing path instead of one per backend.
"""

import argparse


from PIL import Image, ImageDraw

from headline import CANVAS_H, CANVAS_W, TEXT_TOP, draw_headline, headline_bottom

# Vertical breathing room around the refilled band, in canvas pixels. The model's own
# text lands close to the scaffold's but not exactly on it, so the band has to be a
# little more generous than the text we're about to draw.
BAND_PAD_TOP = 80
BAND_PAD_BOTTOM = 60


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


EDGE_W = 110  # px sampled from each side; headlines stay inside the centre 70%
DEVICE_CLEARANCE = 12  # rows left untouched above the device so its top bezel survives


def row_bg(img, y, nominal):
    """
    The background colour at one row, read from the left and right margins.

    The headline is centre-aligned inside the middle 70% of the canvas, so the outer
    ~110px on each side is always flat background — even after the enhance pass, and
    even where the device intrudes lower down. Sampling there means we never have to
    guess where the artwork starts.

    @param nominal - Declared brand hex, returned when the margins look like artwork
    @returns An (r, g, b) tuple for this row
    """
    xs = list(range(0, EDGE_W, 6)) + list(range(img.width - EDGE_W, img.width, 6))
    px = [img.getpixel((x, y)) for x in xs]
    med = tuple(sorted(p[i] for p in px)[len(px) // 2] for i in range(3))

    # A breakout element or stray artwork in the margin would poison the row.
    # Anything this far from the declared brand colour isn't background.
    if max(abs(med[i] - nominal[i]) for i in range(3)) > 45:
        return nominal
    return med


def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def find_device_top(img, search_from, nominal):
    """
    First row below `search_from` where the centre of the canvas stops being background.

    The band has to erase the model's headline without clipping the device beneath it, and the
    model doesn't put the device exactly where the scaffold did. Probing for a *darkness* drop
    rather than any colour change is what makes this safe: the device is dark, leftover headline
    text is white, so white text can never be mistaken for the device top.

    @returns The device's first row, or the image height if nothing dark was found
    """
    x0, x1 = img.width // 2 - 150, img.width // 2 + 150
    floor = luma(nominal) - 15
    for y in range(search_from, img.height):
        px = [img.getpixel((x, y)) for x in range(x0, x1, 12)]
        if sorted(luma(c) for c in px)[len(px) // 2] < floor:
            return y
    return img.height


def fill_band(draw, img, band_top, band_bottom, nominal):
    """
    Repaint the headline band row by row using the colour the render actually has.

    The enhance pass drifts the background a few points off the declared hex and often
    leaves a faint vertical gradient behind, so a flat fill leaves a visible rectangle
    seam. Matching each row to its own neighbours makes the patch disappear.
    """
    for y in range(band_top, band_bottom + 1):
        draw.line([(0, y), (img.width, y)], fill=row_bg(img, y, nominal))


def crop_to_design_aspect(img):
    """
    Centre-crop a too-wide render down to the design canvas ratio.

    Apple's portrait sizes are narrower than 16:9 (0.461 vs 0.5625), and some backends only
    emit preset aspect ratios. Trimming the sides equally preserves the headline and the
    centred device; stretching would not. A render that already matches is returned untouched.
    """
    target = CANVAS_W / CANVAS_H
    if abs(img.width / img.height - target) < 0.005:
        return img
    if img.width / img.height > target:
        new_w = round(img.height * target)
        x0 = (img.width - new_w) // 2
        return img.crop((x0, 0, x0 + new_w, img.height))
    # Taller than the design ratio — trim the bottom, where the device already bleeds off.
    new_h = round(img.width / target)
    return img.crop((0, 0, img.width, new_h))


def finalize(input_path, bg_hex, verb, desc, output_path, target_w, target_h):
    """
    Crop, resize, and repaint the headline on an enhanced render.

    @param input_path - The AI-enhanced image, any size or aspect
    @param bg_hex - Brand background colour, same one passed to compose.py
    @param verb - Action verb line
    @param desc - Benefit descriptor line
    @param output_path - Where to write the result (.jpg recommended — no alpha channel)
    @param target_w - Final width in px, e.g. 1290 for iPhone 6.7"
    @param target_h - Final height in px, e.g. 2796
    """
    img = crop_to_design_aspect(Image.open(input_path).convert("RGB"))

    # Always restamp on the design canvas so typography stays identical across the
    # 6.5"/6.7"/6.9" variants — only the final downscale differs between them.
    if img.size != (CANVAS_W, CANVAS_H):
        img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

    draw = ImageDraw.Draw(img)

    # Wipe the model's rendition of the headline, then draw ours in its place.
    nominal = hex_to_rgb(bg_hex)
    text_bottom = headline_bottom(verb, desc)
    band_top = max(0, TEXT_TOP - BAND_PAD_TOP)

    # Stop the band short of the device. Padding alone isn't enough — the model routinely draws
    # the device higher than the scaffold's DEVICE_Y, and the device is too narrow to show up in
    # the edge samples, so a fixed pad silently paints over its top bezel.
    device_top = find_device_top(img, text_bottom, nominal)
    band_bottom = min(CANVAS_H - 1, text_bottom + BAND_PAD_BOTTOM, device_top - DEVICE_CLEARANCE)
    band_bottom = max(band_bottom, text_bottom)

    fill_band(draw, img, band_top, band_bottom, nominal)

    draw_headline(draw, verb, desc)

    if (target_w, target_h) != (CANVAS_W, CANVAS_H):
        img = img.resize((target_w, target_h), Image.LANCZOS)

    img.save(output_path, quality=95)
    print(f"✓ {output_path} ({target_w}×{target_h})")


def main():
    p = argparse.ArgumentParser(description="Crop, resize, and restamp an enhanced screenshot")
    p.add_argument("--input", required=True, help="AI-enhanced image path")
    p.add_argument("--bg", required=True, help="Background hex colour (#E31837)")
    p.add_argument("--verb", required=True, help="Action verb (TRACK)")
    p.add_argument("--desc", required=True, help="Benefit descriptor (TRADING CARD PRICES)")
    p.add_argument("--output", required=True, help="Output file path (.jpg — no alpha channel)")
    p.add_argument("--width", type=int, default=CANVAS_W, help="Target width (1290)")
    p.add_argument("--height", type=int, default=CANVAS_H, help="Target height (2796)")
    args = p.parse_args()

    finalize(args.input, args.bg, args.verb, args.desc, args.output, args.width, args.height)


if __name__ == "__main__":
    main()
