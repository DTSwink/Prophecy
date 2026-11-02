"""Add deterministic, fine steel wear to the current Imperial Spear PBR atlas.

Run after make_refined_textures.py (and any gold-only atlas refinements).
Only the four steel rectangles in the upper-left quadrant are replaced.
Gold, lacquer, wood, leather and silk pixels are read from the existing files
and retained exactly. Re-running does not accumulate wear: steel is generated
from the same seed and explicit baseline finishes each time.

No geometry, displacement, opacity or external texture sources are involved.
The small normal slopes describe micrometre-scale scratches, not coarse dents.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear/Textures"
SEED = 27102704

# Art controls. 1.0 is the intended restrained, visibly used steel treatment.
WEAR = 1.0
SCRATCH_DENSITY = 1.0
NORMAL_STRENGTH = 1.0
SCRATCH_DEPTH_MM = 0.008       # 8 micrometres; never changes silhouette.
NORMAL_SLOPE_LIMIT = 0.16     # Prevent isolated texels from looking hammered.
ANTIALIAS = 2

# Each region's UV footprint represents about 130 x 465 mm on the blade.
# The narrow atlas strips therefore get fewer strokes, not bigger scratches.
REGIONS = (
    ("steel", (0, 0, 1024, 2048), (145, 153, 162), 0.425, 1.00),
    ("edge", (1024, 0, 1536, 2048), (207, 216, 225), 0.220, 0.30),
    ("ridge", (1536, 0, 1792, 2048), (191, 202, 212), 0.250, 0.38),
    ("steel_shadow", (1792, 0, 2048, 2048), (52, 61, 70), 0.445, 0.18),
)
FILES = {
    "base": "T_ImperialSpear_BaseColor.png",
    "orm": "T_ImperialSpear_ORM.png",
    "gl": "T_ImperialSpear_NormalGL.png",
    "dx": "T_ImperialSpear_NormalDX.png",
}


def nonsteel_digest(image: Image.Image) -> str:
    """Pixel-level guarantee for every region outside the steel quadrant."""
    digest = hashlib.sha256()
    for box in ((2048, 0, 4096, 2048), (0, 2048, 4096, 4096)):
        digest.update(image.crop(box).tobytes())
    return digest.hexdigest()


def noise_field(rng, w: int, h: int, cell_x: int, cell_y: int) -> np.ndarray:
    """Soft signed noise at a specified texel scale, without a periodic grid."""
    tiny = rng.integers(
        0, 256, (max(2, h // cell_y), max(2, w // cell_x)), dtype=np.uint8
    )
    image = Image.fromarray(tiny).resize((w, h), Image.Resampling.BICUBIC)
    return (np.asarray(image, dtype=np.float32) - 127.5) / 127.5


def scratch_masks(rng, w: int, h: int):
    """Sparse AA hairlines with physical length/direction, across the whole UV."""
    aa = ANTIALIAS
    canvas = Image.new("L", (w * aa, h * aa))
    draw = ImageDraw.Draw(canvas)
    mm_x, mm_y = 130.0 / w, 465.0 / h
    density = (w * h) / (1024 * 2048) * SCRATCH_DENSITY
    groups = (
        # count, median length/mm, max length/mm, angular deviation from axis
        (round(6800 * density), 2.4, 12.0, "axial"),
        (round(650 * density), 2.0, 7.0, "cross"),
        (round(65 * density), 10.0, 27.0, "long"),
    )
    total = 0
    for count, median, maximum, direction in groups:
        for _ in range(count):
            x = rng.uniform(0, w)
            y = rng.uniform(0, h)
            length = float(np.clip(rng.lognormal(math.log(median), 0.58), 0.65, maximum))
            if direction == "cross":
                angle = math.radians(rng.uniform(28, 76)) * rng.choice((-1, 1))
            elif direction == "long":
                angle = math.radians(rng.normal(0, 2.8))
            else:
                angle = math.radians(rng.normal(0, 7.0))
            dx = math.sin(angle) * length / mm_x
            dy = math.cos(angle) * length / mm_y
            intensity = int(rng.integers(65, 215 if direction == "long" else 240))
            # Most cuts are sub-texel; a few slightly wider scuffs survive mips.
            width = 1 if rng.random() < 0.78 else 2
            start = ((x - dx * .5) * aa, (y - dy * .5) * aa)
            end = ((x + dx * .5) * aa, (y + dy * .5) * aa)
            draw.line((start, end), fill=intensity, width=width)
            total += 1
    scratch_image = canvas.resize((w, h), Image.Resampling.LANCZOS)
    # Shallow, wider abrading around cuts affects roughness more than color.
    abrasion_image = scratch_image.filter(ImageFilter.GaussianBlur(1.25))
    scratch = np.asarray(scratch_image, dtype=np.float32) / 255.0
    abrasion = np.asarray(abrasion_image, dtype=np.float32) / 255.0
    return scratch, abrasion, total


def make_region(index: int, name: str, box, color, base_roughness: float, local_wear: float):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    rng = np.random.default_rng(SEED + 997 * index)
    strength = WEAR * local_wear
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    grain = noise_field(rng, w, h, 3, 4)
    small_mottle = noise_field(rng, w, h, 12, 16)
    broad_mottle = noise_field(rng, w, h, 46, 62)
    brush = noise_field(rng, w, h, 2, 90)
    scratches, abrasion, stroke_count = scratch_masks(rng, w, h)

    # Used steel stays silver: no brown rust, painted-on holes or large cloudy
    # bump structures. Scratches affect reflected light through roughness and
    # a small real tangent-normal slope as well as restrained albedo contrast.
    tone = 1 + strength * (
        grain * .040 + small_mottle * .027 + broad_mottle * .012
        + brush * .012 + fine * .005 - scratches * .105
    )
    rgb = np.uint8(np.clip(
        tone[:, :, None] * np.asarray(color, dtype=np.float32)[None, None, :],
        0, 255,
    ))
    roughness = base_roughness + strength * (
        grain * .026 + small_mottle * .031 + broad_mottle * .020
        + brush * .019 + fine * .003 + scratches * .135 + abrasion * .10
    )
    packed = np.empty((h, w, 3), dtype=np.uint8)
    packed[:, :, 0] = 255
    packed[:, :, 1] = np.rint(np.clip(roughness, .12, .65) * 255).astype(np.uint8)
    packed[:, :, 2] = 255

    # Millimetres keep scratch depth meaningful at the documented UV scale.
    # Very fine nonperiodic micrograin avoids the flat freshly-chromed finish.
    height_mm = strength * (
        grain * .00055 + brush * .00025
        - scratches * SCRATCH_DEPTH_MM - abrasion * .0015
    )
    dy, dx = np.gradient(height_mm, 465.0 / h, 130.0 / w)
    nx = np.clip(-dx * NORMAL_STRENGTH, -NORMAL_SLOPE_LIMIT, NORMAL_SLOPE_LIMIT)
    # Image rows point downward; tangent-space V points upward.
    ny = np.clip(dy * NORMAL_STRENGTH, -NORMAL_SLOPE_LIMIT, NORMAL_SLOPE_LIMIT)
    length = np.sqrt(nx * nx + ny * ny + 1)
    gl = np.rint(np.clip(
        np.stack((nx / length, ny / length, 1 / length), axis=-1) * 127.5 + 127.5,
        0, 255,
    )).astype(np.uint8)
    dx_normal = gl.copy()
    dx_normal[:, :, 1] = 255 - dx_normal[:, :, 1]
    report = {
        "region": name, "scratch_strokes": stroke_count,
        "roughness_min_max": [float(roughness.min()), float(roughness.max())],
        "normal_max_lateral_component": float(max(np.abs(nx).max(), np.abs(ny).max())),
    }
    return {"base": rgb, "orm": packed, "gl": gl, "dx": dx_normal}, report


def main():
    images = {}
    for key, filename in FILES.items():
        with Image.open(OUT / filename) as source:
            if source.size != (4096, 4096) or source.mode != "RGB":
                raise ValueError(f"Unexpected atlas format: {filename}, {source.size}, {source.mode}")
            images[key] = source.copy()
    protected = {key: nonsteel_digest(image) for key, image in images.items()}
    reports = []
    for index, spec in enumerate(REGIONS):
        generated, report = make_region(index, *spec)
        box = spec[1]
        for key, array in generated.items():
            images[key].paste(Image.fromarray(array), box)
        reports.append(report)
        del generated
    for key, image in images.items():
        assert nonsteel_digest(image) == protected[key], f"Non-steel pixels changed in {key}"
    # Stage all four PNGs before replacing any existing atlas file.
    temporary = []
    try:
        for key, filename in FILES.items():
            path = OUT / (filename + ".wear-tmp.png")
            images[key].save(path, compress_level=3)
            temporary.append((path, OUT / filename))
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for path, _ in temporary:
            path.unlink(missing_ok=True)
    report = {
        "status": "steel wear generated",
        "nonsteel_pixels_unchanged": True,
        "nonsteel_sha256": protected,
        "wear": WEAR, "density": SCRATCH_DENSITY,
        "scratch_depth_mm": SCRATCH_DEPTH_MM,
        "regions": reports,
    }
    (OUT.parent / 'Steel_Texture_Verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
