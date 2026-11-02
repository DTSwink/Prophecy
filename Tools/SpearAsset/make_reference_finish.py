"""Reference-directed material finish pass; no Blender or geometry operations.

Run once to create an immutable backup, then generate the finish from that
backup on every run. Use --restore to restore its four original PNG files.
The silk rectangle is preserved pixel-for-pixel. The former lacquer strip is
split into upper-half beads and lower-half rough cord; geometry must remap UVs.
All RGB values below are sRGB bytes, roughness and packed ORM are linear.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear"
TEXTURES = OUT / "Textures"
BACKUP = ROOT / "Saved/Diagnostics/ImperialSpear/BeforeReferenceFinish_v1"
FILES = {
    "base": "T_ImperialSpear_BaseColor.png",
    "orm": "T_ImperialSpear_ORM.png",
    "gl": "T_ImperialSpear_NormalGL.png",
    "dx": "T_ImperialSpear_NormalDX.png",
}
SEED = 27102706
GOLD_RGB = (165, 129, 70)
GOLD_ROUGHNESS = .465
GOLD_SCRATCH_DEPTH_MM = .0035
WOOD_RGB = (34, 11, 10)
WOOD_ROUGHNESS = .675
LEATHER_RGB = (48, 14, 15)
CORD_RGB = (58, 9, 13)
CORD_ROUGHNESS = .785
BEAD_RGB = (48, 5, 8)
BEAD_ROUGHNESS = .265
BOXES = {
    "gold": (2048, 0, 3072, 2048),
    "gold_shadow": (3072, 0, 3328, 2048),
    "gold_etched": (3584, 0, 4096, 2048),
    "wood": (0, 2048, 2048, 4096),
    "leather": (2048, 2048, 3072, 4096),
    "beads": (3328, 0, 3584, 1024),
    "cord": (3328, 1024, 3584, 2048),
}
SILK = (3072, 2048, 4096, 4096)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_backup():
    manifest_path = BACKUP / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for filename, checksum in manifest["files"].items():
            if file_hash(BACKUP / filename) != checksum:
                raise RuntimeError(f"Immutable backup verification failed: {filename}")
        return manifest
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup exists; inspect it before continuing: {BACKUP}")
    # Preserve compressed original files exactly before preparing any output.
    BACKUP.mkdir(parents=True, exist_ok=False)
    manifest = {"source": str(TEXTURES), "files": {}}
    for filename in FILES.values():
        source, destination = TEXTURES / filename, BACKUP / filename
        shutil.copy2(source, destination)
        checksum = file_hash(source)
        if file_hash(destination) != checksum:
            raise RuntimeError(f"Backup copy failed verification: {filename}")
        manifest["files"][filename] = checksum
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def field(rng, w, h, cell_x, cell_y):
    tiny = rng.integers(0, 256, (max(2, h // cell_y), max(2, w // cell_x)), dtype=np.uint8)
    im = Image.fromarray(tiny).resize((w, h), Image.Resampling.BICUBIC)
    return (np.asarray(im, dtype=np.float32) - 127.5) / 127.5


def scratch_mask(rng, w, h, count, axial=True):
    im = Image.new("L", (w * 2, h * 2))
    draw = ImageDraw.Draw(im)
    for _ in range(count):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        length = rng.uniform(3, 32)
        dx = rng.uniform(-3, 3) if axial else rng.uniform(-length, length)
        draw.line((x * 2, y * 2, (x + dx) * 2, (y + length) * 2),
                  fill=int(rng.integers(60, 180)), width=1)
    return np.asarray(im.resize((w, h), Image.Resampling.LANCZOS), dtype=np.float32) / 255


def normal_from_height(height_mm, physical_mm, existing=None, max_slope=.16):
    h, w = height_mm.shape
    dy, dx = np.gradient(height_mm, physical_mm[1] / h, physical_mm[0] / w)
    nx, ny = -dx, dy
    if existing is not None:
        # Preserve the existing physical-depth engraving normal, adding only
        # micro-wear slopes. Neutral128 is intentionally decoded as zero.
        old = (existing.astype(np.float32) - 128) / 127
        nz = np.maximum(old[:, :, 2], .15)
        nx = nx + old[:, :, 0] / nz
        ny = ny + old[:, :, 1] / nz
    nx = np.clip(nx, -max_slope, max_slope)
    ny = np.clip(ny, -max_slope, max_slope)
    inv = 1 / np.sqrt(nx * nx + ny * ny + 1)
    gl = np.rint(np.clip(np.stack((nx * inv, ny * inv, inv), -1) * 127 + 128, 0, 255)).astype(np.uint8)
    dx_map = gl.copy()
    dx_map[:, :, 1] = 255 - dx_map[:, :, 1]
    return gl, dx_map


def pack(color, tone, roughness, height_mm, physical_mm, metal=0, old_normal=None, max_slope=.16):
    base = np.rint(np.clip(tone[:, :, None] * np.asarray(color, dtype=np.float32), 0, 255)).astype(np.uint8)
    orm = np.empty_like(base)
    orm[:, :, 0] = 255
    orm[:, :, 1] = np.rint(np.clip(roughness, 0, 1) * 255).astype(np.uint8)
    orm[:, :, 2] = np.rint(np.clip(metal, 0, 1) * 255).astype(np.uint8)
    gl, dx = normal_from_height(height_mm, physical_mm, old_normal, max_slope)
    return {"base": base, "orm": orm, "gl": gl, "dx": dx}


def gold_finish(name, old, rng):
    h, w = old["base"].shape[:2]
    grain = field(rng, w, h, 3, 5)
    finish = field(rng, w, h, 22, 35)
    brush = field(rng, w, h, 3, 180)
    scratch = scratch_mask(rng, w, h, round(w * h / 1200), axial=False)
    # No cloudy height field. Mild finish variation is mostly roughness;
    # sparse tarnish subtly desaturates/darkens the metal, not green blotches.
    patina = np.clip((finish - .32) / .65, 0, .4)
    cut = np.zeros((h, w), dtype=np.float32)
    if name == "gold_etched":
        cut = np.clip((old["orm"][:, :, 1].astype(np.float32) / 255 - .346) / .095, 0, 1)
    shadow = name == "gold_shadow"
    color = (76, 50, 21) if shadow else GOLD_RGB
    rough = (.61 if shadow else GOLD_ROUGHNESS) + finish * .035 + grain * .014 + scratch * .08 + cut * .13 + patina * .09
    tone = 1 + grain * .013 + brush * .012 + finish * .024 - scratch * .065 - cut * .23 - patina * .18
    height = grain * .00035 + brush * .0004 - scratch * GOLD_SCRATCH_DEPTH_MM
    # Surface dirt can suppress metal reflectance in dark recesses; exposed
    # gold remains fully metallic. It is not assigned a plastic coat layer.
    metal = (1 - cut * .08 - patina * .12) if not shadow else np.full((h, w), .91, dtype=np.float32)
    physical = (122.5, 181) if name == "gold_etched" else (110, 180)
    return pack(color, tone, rough, height, physical, metal,
                old["gl"] if name == "gold_etched" else None,
                .9 if name == "gold_etched" else .12)


def wood_finish(old, rng):
    h, w = old["base"].shape[:2]
    # Fine longitudinal fibres and sparse pores, without sinusoidal rings,
    # coarse mottled bumps, or a painted broad highlight in the base color.
    fibres = field(rng, w, h, 3, 650)
    bands = field(rng, w, h, 13, 1000)
    fine = field(rng, w, h, 2, 5)
    pores = scratch_mask(rng, w, h, 2800)
    tone = 1 + fibres * .15 + bands * .065 + fine * .012 - pores * .20
    rough = WOOD_ROUGHNESS + fibres * .025 + fine * .013 + pores * .045
    height = fibres * .002 + fine * .0003 - pores * .007
    return pack(WOOD_RGB, tone, rough, height, (100, 1570), max_slope=.10)


def leather_finish(old, rng, cord=False):
    h, w = old["base"].shape[:2]
    grain = field(rng, w, h, 3, 4)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    fibre = field(rng, w, h, 2, 20)
    tone = 1 + grain * .04 + fibre * .024 + fine * .004
    rough = (CORD_ROUGHNESS if cord else .72) + grain * .026 + fine * .003
    height = grain * (.002 if cord else .005) + fibre * .0007
    return pack(CORD_RGB if cord else LEATHER_RGB, tone, rough, height,
                (13, 105) if cord else (114, 240), max_slope=.09)


def bead_finish(old, rng):
    h, w = old["base"].shape[:2]
    finish = field(rng, w, h, 20, 30)
    tone = 1 + finish * .025
    rough = BEAD_ROUGHNESS + finish * .008
    return pack(BEAD_RGB, tone, rough, np.zeros((h, w), dtype=np.float32), (63, 34))


def steel_finish(old, kind):
    out = {key: a.copy() for key, a in old.items()}
    colors = {"steel": ((145, 153, 162), (148, 152, 157), .025),
              "edge": ((207, 216, 225), (193, 201, 210), .075),
              "ridge": ((191, 202, 212), (184, 194, 203), .055),
              "steel_shadow": ((52, 61, 70), (52, 59, 66), .025)}
    source, target, rough_add = colors[kind]
    scale = np.asarray(target, dtype=np.float32) / np.asarray(source, dtype=np.float32)
    out["base"] = np.rint(np.clip(old["base"].astype(np.float32) * scale, 0, 255)).astype(np.uint8)
    out["orm"][:, :, 1] = np.rint(np.clip(old["orm"][:, :, 1].astype(np.float32) + rough_add * 255, 0, 255)).astype(np.uint8)
    # Retain exact existing scratched normals and metallic data.
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true", help="Restore original backed-up PNGs exactly")
    args = parser.parse_args()
    manifest = prepare_backup()
    if args.restore:
        for filename in FILES.values():
            shutil.copy2(BACKUP / filename, TEXTURES / filename)
        print(json.dumps({"status": "original textures restored", "backup": str(BACKUP)}, indent=2))
        return
    images = {}
    for key, filename in FILES.items():
        with Image.open(BACKUP / filename) as im:
            if im.size != (4096, 4096) or im.mode != "RGB":
                raise ValueError(f"Unexpected atlas format: {filename}")
            images[key] = im.copy()
    protected = {key: hashlib.sha256(im.crop(SILK).tobytes()).hexdigest() for key, im in images.items()}
    report = {"backup": str(BACKUP), "backup_files": manifest["files"], "seed": SEED, "regions": {}}
    boxes = {"steel": (0, 0, 1024, 2048), "edge": (1024, 0, 1536, 2048),
             "ridge": (1536, 0, 1792, 2048), "steel_shadow": (1792, 0, 2048, 2048), **BOXES}
    for index, (name, box) in enumerate(boxes.items()):
        old = {key: np.asarray(im.crop(box)) for key, im in images.items()}
        rng = np.random.default_rng(SEED + index * 997)
        if name in ("steel", "edge", "ridge", "steel_shadow"):
            patch = steel_finish(old, name)
        elif name.startswith("gold"):
            patch = gold_finish(name, old, rng)
        elif name == "wood":
            patch = wood_finish(old, rng)
        elif name in ("leather", "cord"):
            patch = leather_finish(old, rng, name == "cord")
        else:
            patch = bead_finish(old, rng)
        report["regions"][name] = {
            "pixels": list(box), "base_mean_srgb": np.round(patch["base"].mean(axis=(0, 1)), 2).tolist(),
            "roughness_min_mean_max": [round(float(patch["orm"][:, :, 1].min()) / 255, 4),
                                       round(float(patch["orm"][:, :, 1].mean()) / 255, 4),
                                       round(float(patch["orm"][:, :, 1].max()) / 255, 4)],
        }
        for key, pixels in patch.items():
            images[key].paste(Image.fromarray(pixels), box)
        del old, patch
    report["silk_pixels_unchanged"] = all(hashlib.sha256(im.crop(SILK).tobytes()).hexdigest() == protected[key] for key, im in images.items())
    assert report["silk_pixels_unchanged"]
    report["depths_mm"] = {"gold_scratches": GOLD_SCRATCH_DEPTH_MM, "wood_pores": .007,
                           "existing_socket_engraving": .10, "steel_scratches_retained": .008}
    report["required_uv_regions"] = {"beads": [.8125, .875, .75, 1], "cord": [.8125, .875, .5, .75]}
    temporary = []
    try:
        for key, filename in FILES.items():
            path = TEXTURES / (filename + ".finish-tmp.png")
            images[key].save(path, compress_level=3)
            temporary.append((path, TEXTURES / filename))
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for path, _ in temporary:
            path.unlink(missing_ok=True)
    report["status"] = "reference finish generated"
    (OUT / "Reference_Finish_Verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
