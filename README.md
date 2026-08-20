# ASO App Store Screenshots

A Claude Code skill that builds App Store screenshots for your iOS app. It reads your codebase to work out what the app is actually good at, pairs those benefits with your simulator screenshots, and hands back finished images at Apple's exact dimensions.

Forked from [adamlyttleapps/claude-skill-aso-appstore-screenshots](https://github.com/adamlyttleapps/claude-skill-aso-appstore-screenshots). The workflow and the prompt design are his and they're good. What changed here is the image backend, the font handling, and one opinionated change to how headline text gets rendered. Full list in [What's different](#whats-different-from-upstream).

## What it does

1. **Benefit discovery** — reads your codebase and pulls out the 3-5 benefits that actually drive downloads
2. **Screenshot pairing** — reviews your simulator screenshots, rates them, pairs each with the benefit it sells best
3. **Generation** — three stages per screenshot: a deterministic scaffold, an AI enhance pass, then a finalize pass that crops, resizes, and repaints the headline
4. **Showcase** — a side-by-side preview of the finished set

Progress is saved to Claude Code's memory between phases, so you can walk away mid-set and pick it up in a new conversation.

## Install

### 1. The skill

```bash
npx skills add gabelul/claude-skill-aso-appstore-screenshots
```

That installs into the current project. Add `-g` to install it globally instead.

### 2. Pillow

```bash
pip install Pillow
```

That's the only Python dependency. Everything else is stdlib.

### 3. An image backend

The enhance stage needs an image model. Two work, and the skill checks for them in this order:

**pixeltamer, preferred.** Full disclosure, I wrote it, which is exactly why I'd rather tell you what it does than sell it:

```bash
npx skills add gabelul/pixeltamer-gpt-image-skill -g
pixeltamer doctor
```

It drives gpt-image-2, and the reason it's the default here is the second backend: if you have a ChatGPT Plus subscription, it goes through the codex CLI and you never touch an API key. Log in with `codex login` and you're done. If you'd rather use an OpenAI key, it takes one of those too, and `doctor` will tell you which paths are live. Repo and full docs: [gabelul/pixeltamer-gpt-image-skill](https://github.com/gabelul/pixeltamer-gpt-image-skill).

Two things about it that matter for this pipeline specifically, both of which cost me an afternoon to find out:

- `edit` takes exactly one `-i`. Two or more references is `compose`. (Fixed in pixeltamer 0.5.6, where `--help` finally says so.)
- `--size` only applies to `generate`. On the codex backend an edit comes back at the input's aspect ratio at roughly 850px on the short edge, whatever you asked for. `finalize.py` upscales from there, and since it repaints the headline afterwards, the upscale never touches your type. 0.5.6 warns you about this instead of letting you find out.

**Gemini MCP, the alternative.** If you've already got an MCP exposing `generate_image` and `edit_image` for Nano Banana Pro, the skill will use it. Wire it into `~/.claude/settings.json` or a project `.mcp.json` and restart Claude Code.

If neither is available the skill says so plainly and offers to build scaffolds only. Flat layouts, no photoreal device, but real files you can look at.

### 4. Fonts, optional

Headlines want **SF Pro Display Black**, from [Apple's developer fonts](https://developer.apple.com/fonts/). If you don't have it the skill uses the system variable font at `/System/Library/Fonts/SFNS.ttf` pinned to the same weight, which looks close enough that you'd need the two side by side to call it. Install Apple's pack later and it goes back to using that with no code change.

## Usage

From inside your app's project:

```
/aso-appstore-screenshots
```

It walks you through each phase and asks before it commits to anything expensive.

## How it works

### Scaffold, enhance, finalize

Generating a whole screenshot from a text prompt gives you a different layout every time, which is useless when the set has to look like a set. So the layout never goes near the model:

1. **`compose.py`** draws a scaffold: exact headline text at exact coordinates, device frame, your simulator screenshot composited into the screen. Pixel-perfect and completely deterministic.
2. **The image backend** takes that scaffold and makes it look expensive. Photoreal device, depth, breakout panels, the polish a designer would add.
3. **`finalize.py`** crops to Apple's aspect ratio, resizes to exact pixel dimensions, and repaints the headline.

The first approved screenshot then becomes the style reference for every one after it, so the whole set comes out looking like it was made in one sitting.

### Why the headline gets repainted

This is the part I'd argue about if someone told me it was over-engineering.

Image models don't preserve text. They *re-render* it. Send a headline through an enhance pass and it comes back with subtly different letterforms, and then you upscale that and it picks up ringing on every edge. On the largest, most conversion-critical element of the screenshot. I only caught it by cropping the output at 1:1 and putting it next to the scaffold, because at preview size it looks fine.

So the model does the artwork and Pillow owns the type. `headline.py` is the single source of truth, used by the scaffold and again by the finalize pass, which means typography comes out pixel-identical across a whole set for free.

Two details in there took measuring to get right, and both are the kind of thing that looks fine until it doesn't:

**The band behind the headline is sampled, not filled.** The enhance pass drifts your background colour a few points and leaves a faint gradient behind even when the prompt tells it not to. Refilling with the hex you asked for leaves a visible rectangle. It now reads the actual colour per row from the left and right margins, which are always background because the headline is centred.

**The band's bottom edge is found, not padded.** The model puts the device wherever it likes. Across three runs of one prompt I got y=698, 718 and 719. A fixed padding value quietly shaved the top bezel off the phone, and because the device never reaches the margins where the colour sampling happens, nothing caught it. `find_device_top` probes the centre for a drop in luminance instead: the device is dark, leftover headline text is white, so text can never be mistaken for the phone.

## Output

```
screenshots/
  01-benefit-slug/
    scaffold.png            ← compose.py, deterministic
    v1.png v2.png v3.png    ← raw backend output, three to choose from
    v1-resized.jpg …        ← finalize.py: cropped, resized, headline repainted
  final/                    ← the approved one per benefit, ready to upload
    01-benefit-slug.jpg
  showcase.png
```

`final/` holds JPEGs at exact Apple dimensions, 1290×2796 by default for the 6.7" iPhone. JPEG on purpose: App Store Connect rejects PNGs carrying an alpha channel and image backends hand those back more often than you'd like.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | The skill prompt, defines the multi-phase workflow |
| `compose.py` | Deterministic scaffold generator |
| `headline.py` | Headline typography, shared by the scaffold and finalize passes |
| `finalize.py` | Crop to aspect, resize to exact dimensions, repaint the headline |
| `fonts.py` | Font loading with the system-font fallback |
| `showcase.py` | Side-by-side preview of the set |
| `generate_frame.py` | Regenerates the device frame template |
| `assets/device_frame.png` | Pre-rendered iPhone frame |

## What's different from upstream

**Font fallback.** Upstream hardcodes `/Library/Fonts/SF-Pro-Display-{Black,Regular}.otf`. Those ship with Apple's downloadable font pack, not with macOS, so on a clean machine every run died at `OSError: cannot open resource` with nothing pointing at fonts as the cause. Sent back upstream as a standalone PR, since it's a plain bug fix that helps everyone.

**Backend routing.** The enhance stage used to require a Gemini MCP. It now prefers pixeltamer and falls back to Gemini.

**`finalize.py` replaces the `sips` crop loop**, and repaints the headline while it's there. See above for why.

If you re-pull from upstream, merge rather than overwrite. Files added: `fonts.py`, `headline.py`, `finalize.py`. Files changed: `compose.py`, `showcase.py`, `SKILL.md`.

### Known corner case

`fill_band` assumes the headline band is background and nothing else. If a breakout element ever climbs up into it, the band will either paint over that element or stripe those rows with the flat brand colour. The enhance prompts keep breakouts down around the device so it hasn't happened yet. Writing it down rather than building for it.

## Credit

Original skill by [Adam Lyttle](https://github.com/adamlyttleapps). MIT, same as it was.
