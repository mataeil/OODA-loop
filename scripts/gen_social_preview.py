#!/usr/bin/env python3
"""Generate docs/social-preview.png — the 1280x640 card GitHub/X/Reddit show when
the repo link is shared. Upload it via GitHub → Settings → Social preview (a
human, UI-only step). Requires Pillow + macOS SF Mono / Menlo.

    python3 scripts/gen_social_preview.py
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "social-preview.png"
W, H = 1280, 640

BG = (13, 17, 23)
PANEL = (17, 22, 29)
BORDER = (48, 54, 61)
WHITE = (240, 246, 252)
TXT = (201, 209, 217)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
CYAN = (86, 212, 221)
BLUE = (88, 166, 255)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

FP = ["/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Menlo.ttc"]
FP_B = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/SFNSRounded.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/SFNSMono.ttf"]


def font(paths, size):
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=18, outline=BORDER, width=2)

    title = font(FP_B, 72)
    tag = font(FP_B, 30)
    mono = font(FP, 25)
    mono_sm = font(FP, 22)
    chip = font(FP_B, 22)

    M = 64
    # wordmark
    d.text((M, 54), "OODA-loop", font=title, fill=WHITE)
    # category line
    d.text((M, 142), "An autonomous operations layer for your live side project.", font=tag, fill=BLUE)
    # hook
    d.text((M, 184), "It opens a small PR at 3am — and re-aims from which ones you merge.", font=tag, fill=DIM)

    # terminal panel with a mini Cycle Card (the differentiator: the LEARN line)
    px0, py0, px1, py1 = M, 250, W - M, 512
    d.rounded_rectangle((px0, py0, px1, py1), radius=14, fill=PANEL, outline=BORDER, width=1)
    bar_h = 40
    d.rounded_rectangle((px0, py0, px1, py0 + bar_h), radius=14, fill=(22, 27, 34))
    d.rectangle((px0, py0 + bar_h - 14, px1, py0 + bar_h), fill=(22, 27, 34))
    for i, c in enumerate(DOTS):
        d.ellipse((px0 + 18 + i * 22, py0 + bar_h // 2 - 6, px0 + 18 + i * 22 + 12, py0 + bar_h // 2 + 6), fill=c)
    d.text((px0 + 96, py0 + 9), "fwd.page · OODA-loop cycle #152", font=mono_sm, fill=DIM)
    # accent rail
    d.rounded_rectangle((px0, py0 + bar_h + 8, px0 + 5, py1 - 8), radius=3, fill=CYAN)

    x = px0 + 28
    y = py0 + bar_h + 22
    LH = 38

    def seg(y, parts):
        cx = x
        for t, c in parts:
            d.text((cx, y), t, font=mono, fill=c)
            cx += mono.getlength(t)

    seg(y + 0 * LH, [("ACT     ", GREEN), ('opened PR #29 — "wrap flaky suite in retry" · draft, you merge', TXT)])
    seg(y + 1 * LH, [("LEARN   ", CYAN), ("you rejected PR #28 → ", TXT), ("service_health 0.74 → 0.54 ↓", RED)])
    seg(y + 2 * LH, [("        ", CYAN), ("lens re-aimed → flaky-alert threshold ", TXT), ("0.30 → 0.25", CYAN)])
    seg(y + 3 * LH, [("COST    ", DIM), ("+$0.04 · hard cap $10 (auto-HALTs) · you stay in command", DIM)])

    # footer: repo + chips
    d.text((M, 552), "github.com/mataeil/OODA-loop", font=chip, fill=WHITE)
    chips = "MIT · Claude Code plugin · Built on Boyd's OODA loop · HALT + cost cap"
    cw = chip.getlength(chips)
    d.text((W - M - cw, 552), chips, font=chip, fill=DIM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"wrote {OUT} ({W}x{H}, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
