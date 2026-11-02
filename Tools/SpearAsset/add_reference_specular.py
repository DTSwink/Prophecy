"""Pack material specular level in ORM alpha and refine dark red wood only.

No Blender operations. Run after make_reference_finish.py. Existing metal,
bead, leather and silk RGB textures, roughness, metallic and normal maps stay
unchanged. ORM becomes RGBA: AO/Roughness/Metallic/Specular IOR Level.
Shader setup must use Non-Color and CHANNEL_PACKED, connect Alpha only to
Specular IOR Level, and retain an opaque surface. --restore reverses this pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear"
TEXTURES = OUT / "Textures"
BACKUP = ROOT / "Saved/Diagnostics/ImperialSpear/BeforeReferenceSpecular_v1"
FILES = ("T_ImperialSpear_BaseColor.png", "T_ImperialSpear_ORM.png")
WOOD = (0, 2048, 2048, 4096)
LEATHER = (2048, 2048, 3072, 4096)
CORD = (3328, 1024, 3584, 2048)
SEED = 27102707
WOOD_RGB = (50, 19, 20)
WOOD_ROUGHNESS = .835
SPECULAR = {"wood": .20, "leather": .25, "cord": .25, "beads": .50, "metals": .50, "silk": .50}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_sources():
    manifest_path = BACKUP / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for filename, checksum in manifest.items():
            if file_hash(BACKUP / filename) != checksum:
                raise RuntimeError(f"Backup checksum mismatch: {filename}")
        return manifest
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup; inspect before proceeding: {BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for filename in FILES:
        shutil.copy2(TEXTURES / filename, BACKUP / filename)
        manifest[filename] = file_hash(TEXTURES / filename)
        if file_hash(BACKUP / filename) != manifest[filename]:
            raise RuntimeError(f"Backup verification failed: {filename}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def outside_wood_hash(image):
    """Hash RGB only: alpha intentionally differs throughout the packed ORM."""
    digest = hashlib.sha256()
    for box in ((0, 0, 4096, 2048), (2048, 2048, 4096, 4096)):
        digest.update(image.crop(box).convert("RGB").tobytes())
    return digest.hexdigest()


def wood_grain():
    rng = np.random.default_rng(SEED)
    w = h = 2048
    dark, light = Image.new("L", (w, h)), Image.new("L", (w, h))
    # These elongated fibres vary gradually across their length, unlike bands
    # of short isotropic noise. Density and widths remain fine at a100mm wrap.
    for im, count in ((dark, 660), (light, 360)):
        draw = ImageDraw.Draw(im)
        for _ in range(count):
            x = rng.uniform(-10, w + 10)
            y0 = rng.uniform(-h * .4, h * .85)
            length = rng.uniform(h * .28, h * 1.4)
            bend, phase = rng.uniform(1.5, 8), rng.uniform(0, math.tau)
            points = []
            for j in range(25):
                t = j / 24
                y = y0 + t * length
                xx = x + bend * math.sin(t * 2.1 + phase) + 1.5 * math.sin(t * 5 + phase)
                points.append((xx, y))
            draw.line(points, fill=int(rng.integers(60, 220)), width=int(rng.choice((1, 1, 2, 2, 3))))
    dark = np.asarray(dark.filter(ImageFilter.GaussianBlur(.42)), dtype=np.float32) / 255
    light = np.asarray(light.filter(ImageFilter.GaussianBlur(.42)), dtype=np.float32) / 255
    fibre_noise = rng.integers(0, 256, (5, 620), dtype=np.uint8)
    fibre_noise = (np.asarray(Image.fromarray(fibre_noise).resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32) - 127.5) / 127.5
    tone = 1 + fibre_noise * .105 - dark * .34 + light * .21
    base = np.rint(np.clip(tone[:, :, None] * np.asarray(WOOD_RGB, dtype=np.float32), 0, 255)).astype(np.uint8)
    roughness = np.rint(np.clip(WOOD_ROUGHNESS + fibre_noise * .016 + dark * .028 - light * .014, .80, .86) * 255).astype(np.uint8)
    return base, roughness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    backups = backup_sources()
    if args.restore:
        for filename in FILES:
            shutil.copy2(BACKUP / filename, TEXTURES / filename)
        print("Pre-specular BaseColor and ORM restored exactly.")
        return
    base_patch, wood_roughness = wood_grain()
    temporary, protected = [], {}
    try:
        for filename in FILES:
            with Image.open(BACKUP / filename) as source:
                if source.size != (4096, 4096) or source.mode not in ("RGB", "RGBA"):
                    raise ValueError(f"Unexpected atlas format: {filename}")
                image = source.convert("RGBA" if "ORM" in filename else "RGB")
            before = outside_wood_hash(image)
            if "BaseColor" in filename:
                image.paste(Image.fromarray(base_patch), WOOD)
            else:
                alpha = Image.new("L", image.size, round(SPECULAR["metals"] * 255))
                alpha.paste(round(SPECULAR["wood"] * 255), WOOD)
                alpha.paste(round(SPECULAR["leather"] * 255), LEATHER)
                alpha.paste(round(SPECULAR["cord"] * 255), CORD)
                image.putalpha(alpha)
                patch = np.array(image.crop(WOOD))
                patch[:, :, 1] = wood_roughness
                image.paste(Image.fromarray(patch), WOOD)
            after = outside_wood_hash(image)
            assert before == after, f"Protected RGB pixels changed: {filename}"
            protected[filename] = {"before_sha256": before, "after_sha256": after, "unchanged": True}
            path = TEXTURES / (filename + ".specular-tmp.png")
            image.save(path, compress_level=3)
            temporary.append((path, TEXTURES / filename))
            del image
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for path, _ in temporary:
            path.unlink(missing_ok=True)
    report = {
        "status": "reference specular alpha and red wood generated", "backup": str(BACKUP),
        "original_files": backups, "wood_rgb": list(WOOD_RGB), "specular_levels": SPECULAR,
        "wood_roughness_min_mean_max": [round(float(wood_roughness.min()) / 255, 4), round(float(wood_roughness.mean()) / 255, 4), round(float(wood_roughness.max()) / 255, 4)],
        "preserved_rgb_outside_wood": protected, "normal_maps_modified": False,
        "channel_layout": "R AO, G Roughness, B Metallic, A Specular IOR Level",
        "blender_image_settings": {"colorspace": "Non-Color", "alpha_mode": "CHANNEL_PACKED", "opaque_surface": True},
    }
    (OUT / "Reference_Specular_Verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
