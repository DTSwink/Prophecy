"""Chased leaf/flame engraving for the existing gold socket atlas region.

Run only when ready to update the PBR textures. This script changes the
gold_etched rectangle, pixels (3584, 0)..(4096, 2048), and no other pixels.
The pattern is cut into the surface in tangent normals: it is not a raised
wire pattern. Steel wear, other gold finishes, lacquer, wood, leather and silk
are retained from the current files exactly. Re-running is deterministic.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear/Textures"
BOX = (3584, 0, 4096, 2048)
WIDTH, HEIGHT = 512, 2048
CIRCUMFERENCE_MM = 122.5
AXIAL_SPAN_MM = 181.0

# Intentional engraving scale, independent of the texture's unequal U/V density.
COLUMNS = 8
ROWS = 12
OUTER_STROKE_MM = 0.46
MID_STROKE_MM = 0.33
CORE_STROKE_MM = 0.17
CUT_DEPTH_MM = 0.10
VEIN_WIDTH_SCALE = 0.72
POLISHED_LIP_MM = 0.075
NORMAL_STRENGTH = 1.0
NORMAL_SLOPE_LIMIT = 0.85
DRAW_PIXELS_PER_MM = 16
SEED = 27102705

FILES = {
    "base": "T_ImperialSpear_BaseColor.png",
    "orm": "T_ImperialSpear_ORM.png",
    "gl": "T_ImperialSpear_NormalGL.png",
    "dx": "T_ImperialSpear_NormalDX.png",
}


def bezier(p0, p1, p2, p3, steps=12):
    """Sample cubic strokes; adjoining unequal tangents retain pointed cusps."""
    result = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        result.append((
            a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
        ))
    return result


def leaf_paths():
    """Opposed flame/leaf contours with sharp terminals and one fine internal cut."""
    # One flame occupies the left half of a ~15.3 x 15.1mm repeating cell.
    # The opposing flame is the 180-degree counterpart, never an oval/circle.
    outline = []
    segments = (
        ((-5.6, -6.35), (-5.15, -2.9), (-1.55, -2.55), (-1.45, 0.0)),
        ((-1.45, 0.0), (-2.15, 2.1), (-4.45, 2.95), (-5.7, 5.35)),
        ((-5.7, 5.35), (-6.65, 1.9), (-6.10, -1.55), (-5.6, -6.35)),
    )
    for segment in segments:
        pts = bezier(*segment)
        outline.extend(pts if not outline else pts[1:])
    vein = bezier((-5.48, -5.25), (-4.92, -3.9), (-3.6, -2.85), (-3.18, -1.05), 14)
    vein += bezier((-3.18, -1.05), (-3.02, .48), (-4.50, 2.04), (-5.31, 3.58), 14)[1:]
    return ((outline, 1.0), (vein, VEIN_WIDTH_SCALE))


def engraving_masks():
    """Rasterize in physical space, then resample to the atlas's anisotropic UV."""
    ppm = DRAW_PIXELS_PER_MM
    size = (round(CIRCUMFERENCE_MM * ppm), round(AXIAL_SPAN_MM * ppm))
    cut_image = Image.new("L", size)
    lip_image = Image.new("L", size)
    cut_draw = ImageDraw.Draw(cut_image)
    lip_draw = ImageDraw.Draw(lip_image)
    cell_w = CIRCUMFERENCE_MM / COLUMNS
    cell_h = AXIAL_SPAN_MM / ROWS
    paths = leaf_paths()
    count = 0
    # Extra horizontal cells make the wrap seam continuous when the odd rows
    # are offset. The design repeats over the full circumference exactly.
    for row in range(ROWS):
        offset = .5 if row % 2 else 0.0
        for column in range(-1, COLUMNS + 1):
            cx = (column + .5 + offset) * cell_w
            cy = (row + .5) * cell_h
            for opposite in (1, -1):
                for points, width_scale in paths:
                    mapped = [((cx + opposite * x) * ppm, (cy + opposite * y) * ppm) for x, y in points]
                    lip_width = max(1, round((OUTER_STROKE_MM * width_scale + POLISHED_LIP_MM * 2) * ppm))
                    lip_draw.line(mapped, fill=255, width=lip_width, joint="curve")
                    # Three nested negative-height strokes form bevelled walls
                    # and a narrow deeper centre, instead of a painted outline.
                    for width, value in ((OUTER_STROKE_MM, 70), (MID_STROKE_MM, 163), (CORE_STROKE_MM, 255)):
                        pixels = max(1, round(width * width_scale * ppm))
                        cut_draw.line(mapped, fill=value, width=pixels, joint="curve")
                    count += 1
    cut_image = cut_image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    lip_image = lip_image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    cut = np.asarray(cut_image, dtype=np.float32) / 255.0
    lip = np.asarray(lip_image, dtype=np.float32) / 255.0
    return cut, np.clip(lip - cut * 1.8, 0, 1), count


def generate_region():
    cut, lip, path_count = engraving_masks()
    rng = np.random.default_rng(SEED)
    fine = rng.normal(0, 1, (HEIGHT, WIDTH)).astype(np.float32)
    tiny = rng.integers(0, 256, (128, 32), dtype=np.uint8)
    grain = (np.asarray(Image.fromarray(tiny).resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC), dtype=np.float32) - 127.5) / 127.5

    # Most of the sleeve retains its clean gold finish. Controlled dark cuts
    # and modest brighter lips make small engravings legible under moving light.
    tone = 1.0 + grain * .012 + fine * .0015 - cut * .29 + lip * .045
    color = np.asarray((173, 128, 59), dtype=np.float32)
    base = np.rint(np.clip(tone[:, :, None] * color[None, None, :], 0, 255)).astype(np.uint8)
    roughness = .33 + grain * .010 + fine * .0015 + cut * .115 - lip * .035
    orm = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    orm[:, :, 0] = 255
    orm[:, :, 1] = np.rint(np.clip(roughness, .23, .49) * 255).astype(np.uint8)
    orm[:, :, 2] = 255

    height_mm = -CUT_DEPTH_MM * cut
    dy, dx = np.gradient(height_mm, AXIAL_SPAN_MM / HEIGHT, CIRCUMFERENCE_MM / WIDTH)
    nx = np.clip(-dx * NORMAL_STRENGTH, -NORMAL_SLOPE_LIMIT, NORMAL_SLOPE_LIMIT)
    ny = np.clip(dy * NORMAL_STRENGTH, -NORMAL_SLOPE_LIMIT, NORMAL_SLOPE_LIMIT)
    length = np.sqrt(nx * nx + ny * ny + 1)
    gl = np.rint(np.clip(np.stack((nx / length, ny / length, 1 / length), axis=-1) * 127.5 + 127.5, 0, 255)).astype(np.uint8)
    dx_normal = gl.copy()
    dx_normal[:, :, 1] = 255 - dx_normal[:, :, 1]
    report = {
        "motif_cell_mm": [CIRCUMFERENCE_MM / COLUMNS, AXIAL_SPAN_MM / ROWS],
        "motif_repeat": [COLUMNS, ROWS],
        "engraving_depth_mm": CUT_DEPTH_MM,
        "outer_stroke_width_mm": OUTER_STROKE_MM,
        "internal_vein_width_mm": OUTER_STROKE_MM * VEIN_WIDTH_SCALE,
        "rasterized_paths_including_wrap_bleed": path_count,
        "normal_max_lateral_component": float(max(np.abs(nx).max(), np.abs(ny).max())),
    }
    return {"base": base, "orm": orm, "gl": gl, "dx": dx_normal}, report


def protected_digest(image: Image.Image) -> str:
    """Hash all unchanged pixels in bounded strips to avoid full atlas copies."""
    digest = hashlib.sha256()
    for top in range(0, 4096, 128):
        bottom = min(4096, top + 128)
        digest.update(image.crop((0, top, 3584, bottom)).tobytes())
        if top >= 2048:
            digest.update(image.crop((3584, top, 4096, bottom)).tobytes())
    return digest.hexdigest()


def main():
    region, report = generate_region()
    temporary = []
    preservation = {}
    try:
        # Only one full atlas is held at once. All outputs are staged before
        # replacing any current texture, and protected pixels are verified.
        for key, filename in FILES.items():
            with Image.open(OUT / filename) as source:
                if source.mode != "RGB" or source.size != (4096, 4096):
                    raise ValueError(f"Unexpected atlas format for {filename}")
                image = source.copy()
            before = protected_digest(image)
            image.paste(Image.fromarray(region[key]), BOX)
            after = protected_digest(image)
            assert after == before, f"Pixels outside gold_etched changed in {filename}"
            preservation[filename] = {"before_sha256": before, "after_sha256": after, "unchanged": True}
            path = OUT / (filename + ".engraving-tmp.png")
            image.save(path, compress_level=3)
            temporary.append((path, OUT / filename))
            del image
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for path, _ in temporary:
            path.unlink(missing_ok=True)
    verification = {
        "status": "socket engraving generated",
        "region": list(BOX),
        "all_other_pixels_unchanged": True,
        "protected_pixels": preservation,
        **report,
    }
    report_path = OUT.parent / "Socket_Texture_Verification.json"
    report_path.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
