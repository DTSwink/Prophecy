"""Isolated optical-size study. No edits to runtime fonts, settings or Unreal."""
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1] / "Resources/Fonts/BodoniModa-variable.ttf"
VARIANTS = [(24, "Original"), (16, "A · Gentle"), (10, "B · Medium"), (6, "C · Strong")]
report = []
for size, label in VARIANTS:
    font = instantiateVariableFont(TTFont(SOURCE), {"opsz": size, "wght": 400}, inplace=True)
    font.save(ROOT / f"optical-{size}.ttf")
    c, ends, flags = font["glyf"]["H"].getCoordinates(font["glyf"])
    report.append({
        "label": label, "optical_size": size, "weight": 400,
        "H_crossbar_units": round(c[23][1] - c[9][1], 2),
        "H_main_stem_units": round(c[10][0] - c[16][0], 2),
        "file": f"optical-{size}.ttf"
    })
(ROOT / "metrics.json").write_text(json.dumps(report, indent=2))
(ROOT / "OFL.txt").write_bytes((SOURCE.parent / "OFL.txt").read_bytes())

# Code-rendered proof, not edited concept art. One solid ink color, no effects.
W, H = 1600, 1010
image = Image.new("RGB", (W, H), "#101116")
draw = ImageDraw.Draw(image)
ui = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
heading = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 30)
draw.text((40, 27), "MENU HAIRLINES — SAME FONT, SAME WEIGHT", font=heading, fill="#f2f0eb")
draw.text((40, 75), "Original and three optical-size variants. No outline, shadow, transparency or simulated bold.", font=ui, fill="#b3b3c0")
for i, (size, label) in enumerate(VARIANTS):
    x, y = 40 + (i % 2) * 780, 130 + (i // 2) * 420
    draw.rounded_rectangle((x, y, x+740, y+392), radius=9, fill="#08090c", outline="#33323e")
    draw.text((x+24, y+18), f"{label}  /  optical size {size}", font=ui, fill="#c6b0e2")
    big = ImageFont.truetype(str(ROOT/f"optical-{size}.ttf"), 100)
    normal = ImageFont.truetype(str(ROOT/f"optical-{size}.ttf"), 24)
    def tracked(s, px, py, f, spacing):
        for c in s:
            draw.text((px, py), c, font=f, fill="#f2f0eb", anchor="lt")
            px += draw.textlength(c, font=f) + spacing
    tracked("RESUME", x+24, y+75, big, 7)
    draw.text((x+24, y+191), "24 px · close to menu size", font=small, fill="#838591")
    for j, text in enumerate(("RESUME", "INVENTORY   JOURNAL", "SETTINGS   QUIT TO MENU")):
        tracked(text, x+24, y+228+j*43, normal, 3.705132)
draw.text((40, 985), "PAUSED and the Unreal preview are untouched. Enlarged type exposes shape changes; judge small type at 100%.", font=small, fill="#a5a4af")
image.save(ROOT/"comparison.png")
print(json.dumps(report, indent=2))
