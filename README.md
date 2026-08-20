# ASO App Store Screenshots

A Claude Code skill that generates high-converting App Store screenshots for your iOS app. It analyzes your codebase, identifies core benefits, and creates professional screenshot images using AI.

## What It Does

1. **Benefit Discovery** — Analyzes your app's codebase to identify the 3-5 core benefits that drive downloads
2. **Screenshot Pairing** — Reviews your simulator screenshots, rates them, and pairs each with the best benefit
3. **Generation** — Creates polished App Store screenshots using a two-stage process: deterministic scaffolding (compose.py) + AI enhancement (Nano Banana Pro via Gemini MCP)
4. **Showcase** — Generates a preview image with all screenshots side-by-side

## Installation

### 1. Add the skill to Claude Code

```bash
claude install-skill github.com/adamlyttleapps/claude-skill-aso-appstore-screenshots
```

### 2. Install Python dependencies

```bash
pip install Pillow
```

### 3. Font requirement

The skill uses **SF Pro Display Black** for headline text. On macOS, install it from [Apple's developer fonts](https://developer.apple.com/fonts/). The expected path is:

```
/Library/Fonts/SF-Pro-Display-Black.otf
```

### 4. Set up Gemini MCP (for AI enhancement)

The generation phase requires [@houtini/gemini-mcp](https://www.npmjs.com/package/@houtini/gemini-mcp) to be configured as an MCP server in Claude Code:

```bash
npm install -g @houtini/gemini-mcp
```

Then add it to your Claude Code MCP config (`~/.claude/settings.json` or project `.mcp.json`).

## Usage

From within your app's project directory, run:

```
/aso-appstore-screenshots
```

The skill will guide you through each phase interactively. Progress is saved to Claude Code's memory system, so you can resume across conversations.

## How It Works

### Scaffold → Enhance Pipeline

Rather than generating screenshots from scratch (which produces inconsistent results), the skill uses a two-stage approach:

1. **compose.py** creates a deterministic scaffold with exact text positioning, device frame, and your simulator screenshot composited inside
2. **Nano Banana Pro** (via Gemini MCP) enhances the scaffold — adding a photorealistic device frame, breakout elements, and visual polish

This ensures consistent layout across all screenshots while letting AI handle the creative enhancement.

### Output

Screenshots are saved to a `screenshots/` directory in your project:

```
screenshots/
  01-benefit-slug/          ← working versions
    scaffold.png            ← deterministic compose.py output
    v1.png, v2.png, v3.png  ← AI-enhanced versions
    v1-resized.png, ...     ← cropped to App Store dimensions
  final/                    ← approved screenshots, ready to upload
    01-benefit-slug.png
    02-benefit-slug.png
  showcase.png              ← preview image with all screenshots
```

The `final/` folder contains App Store-ready screenshots at exact Apple dimensions (default: 1290×2796px for iPhone 6.7").

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | The skill prompt — defines the multi-phase workflow |
| `compose.py` | Deterministic scaffold generator (Pillow-based) |
| `generate_frame.py` | Generates the device frame template |
| `showcase.py` | Generates the side-by-side showcase image |
| `assets/device_frame.png` | Pre-rendered iPhone device frame template |

## License

MIT

---

## Local fork notes

This copy diverges from upstream. Re-pulling the repo will clobber these — merge, don't overwrite.

**1. Font fallback (`fonts.py`)** — upstream hardcodes `/Library/Fonts/SF-Pro-Display-{Black,Regular}.otf`,
which only exist if you've downloaded Apple's font pack. On a stock Mac every run died with
`OSError: cannot open resource`. `fonts.py` tries those first and falls back to the system variable font
at `/System/Library/Fonts/SFNS.ttf`, pinned to the requested named weight. Install Apple's pack and it
silently goes back to using it.

**2. Backend-agnostic enhance stage** — the generation phase used to require a Gemini MCP. It now prefers
[pixeltamer](https://github.com/gabelul/pixeltamer) (gpt-image-2 via OpenAI key or the codex CLI) and falls
back to a Gemini MCP. See "Prerequisites Check" in `SKILL.md`.

**3. `finalize.py` replaces the `sips` crop loop** — it centre-crops to Apple's aspect ratio, resizes to
exact dimensions, and **repaints the headline**.

That last part is the one worth understanding. Image models re-render text rather than preserving it, so
the old pipeline shipped headlines with subtly wrong letterforms plus upscaling ringing — on the largest
element of the screenshot. Measured on a real run: the enhanced headline came back visibly soft with halo
artifacts, and the model had quietly redrawn the letterforms. Now the model does the artwork and Pillow
owns the type, via `headline.py` — the same code that drew the scaffold. Typography is pixel-identical
across the whole set as a side effect.

The band behind the headline is repainted by sampling the render's actual background colour per row from
the left/right margins, not by filling the declared hex — the enhance pass drifts the background a few
points and leaves a faint gradient, so a flat fill leaves a visible rectangle seam.

**Files added by the fork**: `fonts.py`, `headline.py`, `finalize.py`.
**Files modified**: `compose.py` (uses `headline.py`), `showcase.py` (uses `fonts.py`), `SKILL.md`.

**Backend gotchas worth knowing** (both found by running it, not reading docs):

- `pixeltamer edit` takes **exactly one** `-i` despite its `--help` saying the flag is repeatable.
  Two or more references need `compose`.
- `pixeltamer --size` is ignored on the codex backend for edits — output comes back at roughly the
  input's aspect, ~850px wide, whatever you ask for. Harmless here: `finalize.py` upscales to Apple's
  dimensions *and then* repaints the headline, so the upscale never touches the type.

**Known corner case**: `fill_band` assumes the headline band contains only background. If a breakout
element ever rises into it, the band will either paint over the element or stripe those rows with the
nominal hex (via the sampling guard). The enhance prompts keep breakouts down at the device, so this
hasn't come up — noted rather than engineered around.
