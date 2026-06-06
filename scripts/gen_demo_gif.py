#!/usr/bin/env python3
"""Generate the README hero animation: docs/demo.gif.

A polished dark-terminal animation of one OODA-loop cycle, ending on the
differentiator — the LEARN line where the agent re-aims from a human reject.
Content mirrors tests/cycle-card/ (fwd.page cycle #152).

Usage:
    python3 scripts/gen_demo_gif.py            # writes docs/demo.gif
    python3 scripts/gen_demo_gif.py --preview  # also writes docs/demo_preview.png (final frame)

Requires Pillow. Font: macOS SF Mono (falls back to Menlo).
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_GIF = ROOT / "docs" / "demo.gif"
OUT_PNG = ROOT / "docs" / "demo_preview.png"

# ---- palette (GitHub dark) ----
BG = (13, 17, 23)            # #0d1117 window
BAR = (22, 27, 34)           # #161b22 title bar
CARD = (17, 22, 29)          # inner card
BORDER = (48, 54, 61)        # #30363d
TXT = (201, 209, 217)        # #c9d1d9
DIM = (110, 118, 129)        # #6e7681
WHITE = (240, 246, 252)
GREEN = (63, 185, 80)        # #3fb950
RED = (248, 81, 73)          # #f85149
CYAN = (86, 212, 221)        # #56d4dd
BLUE = (88, 166, 255)        # #58a6ff
PURPLE = (188, 140, 255)     # #bc8cff
YELLOW = (227, 179, 65)      # #e3b341
GRAY = (139, 148, 158)       # #8b949e

DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

FONT_PATHS = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Menlo.ttc",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


FS = 24
F = load_font(FS)
FB = load_font(FS)  # SF Mono single weight; reuse
LH = 38                       # line height
CW = F.getlength("M")         # monospace char width
PAD = 34
BAR_H = 52
LABEL_W = 10                  # label column chars

# A line = (label, label_color, [(text, color), ...]). label "" = continuation.
PROMPT = [("> ", GREEN), ("/evolve", WHITE), ("  --cycle", DIM)]

CARD_LINES = [
    ("OBSERVE", BLUE, [("4 domains · ", TXT), ("test_coverage 91% -> 84% overnight", TXT)]),
    ("ORIENT", PURPLE, [("flaky-retry pattern confirmed (3rd time);", TXT)]),
    ("", PURPLE, [("coverage is now the most stale + highest-signal domain", DIM)]),
    ("DECIDE", YELLOW, [("test_coverage won  score 11.3 · conf 0.74 · gate ", TXT), ("OK", GREEN)]),
    ("ACT", GREEN, [('opened PR #29 — "wrap flaky network suite in retry"', TXT)]),
    ("", GREEN, [("Risk Tier 1 · 2 files · draft — ", DIM), ("you merge", WHITE)]),
    ("LEARN", CYAN, [("you rejected PR #28  ->  ", TXT), ("service_health 0.74 -> 0.54 ↓", RED)]),
    ("", CYAN, [("(reject ", DIM), ("-0.2", RED), (", 2x faster than a merge's +0.1)", DIM)]),
    ("", CYAN, [("lens re-aimed · flaky-alert threshold ", TXT), ("0.30 -> 0.25", CYAN)]),
    ("COST", GRAY, [("+$0.04 · $0.38 today · hard cap $10 ", DIM), ("-> auto-HALT", GRAY)]),
]
FOOTER = [("HALT ", DIM), ("inactive", GREEN), ("  ·  Level 2 ", DIM), ("(Full observation)", TXT)]
CAPTION = [("You rejected it.  ", WHITE), ("It re-aimed.", CYAN)]

# ---- geometry ----
content_w = 0
for _, _, segs in CARD_LINES:
    w = LABEL_W * CW + sum(F.getlength(t) for t, _ in segs)
    content_w = max(content_w, w)
W = int(PAD * 2 + max(content_w, F.getlength("HALT inactive  ·  Level 2 (Full observation)")) + PAD)
W = max(W, 1000)

# vertical: title bar, prompt, gap, card(top pad + N lines + blank + footer + bot pad), gap, caption
N = len(CARD_LINES)
card_top = BAR_H + PAD + LH + 18
card_inner_lines = N + 2  # + blank + footer
card_h = 22 + card_inner_lines * LH + 22
caption_y = card_top + card_h + 26
H = caption_y + LH + PAD


def seg_line(d, x, y, segs, alpha=255):
    for t, c in segs:
        col = c if alpha == 255 else tuple(int(v) for v in c)
        d.text((x, y), t, font=F, fill=col)
        x += F.getlength(t)
    return x


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def render(reveal: int, cursor: bool, show_caption: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # window border + title bar
    rounded(d, (1, 1, W - 2, H - 2), 14, outline=BORDER, width=2)
    rounded(d, (1, 1, W - 2, BAR_H), 14, fill=BAR)
    d.rectangle((1, BAR_H - 14, W - 2, BAR_H), fill=BAR)
    d.line((1, BAR_H, W - 2, BAR_H), fill=BORDER, width=1)
    for i, c in enumerate(DOTS):
        cx = 26 + i * 26
        d.ellipse((cx, BAR_H // 2 - 7, cx + 14, BAR_H // 2 + 7), fill=c)
    d.text((118, BAR_H // 2 - FS // 2 - 2), "fwd.page · OODA-loop", font=F, fill=DIM)

    # prompt
    py = BAR_H + PAD - 6
    px = seg_line(d, PAD, py, PROMPT)
    if reveal == 0 and cursor:
        d.rectangle((px + 3, py + 4, px + 3 + CW * 0.6, py + FS), fill=GREEN)

    # card frame
    rounded(d, (PAD, card_top, W - PAD, card_top + card_h), 12, fill=CARD, outline=BORDER, width=1)

    # accent rail on the left of the card
    d.rounded_rectangle((PAD, card_top, PAD + 5, card_top + card_h), radius=3, fill=CYAN if reveal > 6 else BORDER)

    ix = PAD + 26
    iy = card_top + 22
    shown = min(reveal, N)
    for i in range(shown):
        label, lcol, segs = CARD_LINES[i]
        y = iy + i * LH
        if label:
            d.text((ix, y), label, font=F, fill=lcol)
        sx = ix + LABEL_W * CW
        ex = seg_line(d, sx, y, segs)
        if cursor and i == shown - 1 and reveal <= N:
            d.rectangle((ex + 3, y + 4, ex + 3 + CW * 0.6, y + FS), fill=lcol)

    # footer (after all card lines revealed)
    if reveal > N:
        fy = iy + (N + 1) * LH
        seg_line(d, ix, fy, FOOTER)

    # caption
    if show_caption:
        cap_w = sum(F.getlength(t) for t, _ in CAPTION)
        seg_line(d, (W - cap_w) // 2, caption_y, CAPTION)

    return img


def build_frames():
    frames, durs = [], []

    def add(img, ms):
        frames.append(img)
        durs.append(ms)

    # 1) prompt blink
    add(render(0, True, False), 360)
    add(render(0, False, False), 240)
    add(render(0, True, False), 360)
    # 2) reveal card lines one by one
    for k in range(1, N + 1):
        add(render(k, True, False), 150 if CARD_LINES[k - 1][0] != "LEARN" else 240)
    # small hold before footer
    add(render(N, False, False), 220)
    # 3) footer + full card hold
    add(render(N + 1, False, False), 500)
    # 4) caption fade-in (appear) + long hold
    add(render(N + 1, False, True), 2400)
    add(render(N + 1, False, False), 500)  # blink caption off->on for a beat
    add(render(N + 1, False, True), 1700)
    return frames, durs


def main() -> int:
    OUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    frames, durs = build_frames()
    if "--preview" in sys.argv:
        render(len(CARD_LINES) + 1, False, True).save(OUT_PNG)
        print(f"wrote {OUT_PNG} ({W}x{H})")
    # quantize for small size
    pal = frames[-1].convert("P", palette=Image.ADAPTIVE, colors=128)
    qframes = [f.convert("RGB").quantize(palette=pal, dither=Image.NONE) for f in frames]
    qframes[0].save(
        OUT_GIF,
        save_all=True,
        append_images=qframes[1:],
        duration=durs,
        loop=0,
        optimize=True,
        disposal=2,
    )
    kb = OUT_GIF.stat().st_size / 1024
    print(f"wrote {OUT_GIF} ({W}x{H}, {len(frames)} frames, {kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
