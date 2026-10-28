"""Generates assets/frametweak.ico and .png (original design: frame brackets + performance pulse)."""
import os
from PIL import Image, ImageDraw
S = 1024; OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle((40, 40, S - 40, S - 40), 230, fill="#10151b", outline="#26323f", width=14)
c, a, L = "#22d3ee", 250, 190
for (x, y, sx, sy) in ((a, a, 1, 1), (S - a, a, -1, 1), (a, S - a, 1, -1), (S - a, S - a, -1, -1)):
    d.line([(x, y + sy * L), (x, y), (x + sx * L, y)], fill=c, width=74, joint="curve")
    for px, py in ((x, y + sy * L), (x + sx * L, y)): d.ellipse((px - 37, py - 37, px + 37, py + 37), fill=c)
pts = [(330, 540), (432, 540), (492, 400), (566, 664), (624, 540), (694, 540)]
d.line(pts, fill="#8b5cf6", width=58, joint="curve")
for p in (pts[0], pts[-1]): d.ellipse((p[0] - 29, p[1] - 29, p[0] + 29, p[1] + 29), fill="#8b5cf6")
os.makedirs(OUT, exist_ok=True)
im.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "frametweak.png"))
im.save(os.path.join(OUT, "frametweak.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
