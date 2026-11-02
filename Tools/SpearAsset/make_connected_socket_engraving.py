"""Connected chased acanthus/chevron pattern in the socket atlas only.

Run after finish/specular passes. Retains RGB/RGBA mode and ORM alpha exactly;
all pixels outside gold_etched stay byte-identical. Physical-depth normal map
replaces isolated leaf icons with connected stems and paired pointed leaves.
No geometry, Blender, external textures or background processes are involved.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear"
TEXTURES = OUT / "Textures"
BACKUP = ROOT / "Saved/Diagnostics/ImperialSpear/BeforeConnectedSocket_v1"
BOX = (3584, 0, 4096, 2048)
W, H = 512, 2048
CIRCUMFERENCE_MM, AXIAL_MM = 122.5, 152.48
COLUMNS, ROWS = 7, 12
STROKE_MM, DEPTH_MM, LIP_MM = 1.2, .15, .14
PIXELS_PER_MM = 14
GOLD_RGB = (158, 124, 76)
SEED = 27102708
FILES = {"base": "T_ImperialSpear_BaseColor.png", "orm": "T_ImperialSpear_ORM.png",
         "gl": "T_ImperialSpear_NormalGL.png", "dx": "T_ImperialSpear_NormalDX.png"}


def bezier(p0, p1, p2, p3):
    points = []
    for t in np.linspace(0, 1, 20):
        points.append(tuple((1-t)**3*p0[i]+3*(1-t)**2*t*p1[i]+3*(1-t)*t*t*p2[i]+t**3*p3[i] for i in range(2)))
    return points


def pattern():
    ppm = PIXELS_PER_MM
    size = (round(CIRCUMFERENCE_MM * ppm), round(AXIAL_MM * ppm))
    cut, lip = Image.new("L", size), Image.new("L", size)
    dc, dl = ImageDraw.Draw(cut), ImageDraw.Draw(lip)
    cell_w, cell_h = CIRCUMFERENCE_MM / COLUMNS, AXIAL_MM / ROWS
    leaves = [bezier((0, 5.1), (-3.8, 1.7), (-5.7, 1.4), (-7.05, -5.6)) +
              bezier((-7.05, -5.6), (-3.5, -2.6), (-1.2, -3.3), (0, 1.0))[1:]]
    vein = bezier((-.5, 3.6), (-2.9, 1.2), (-4.3, -.1), (-5.4, -3.25))

    def stroke(points, cx, cy, scale=1):
        points = [((cx+x)*ppm, (cy+y)*ppm) for x, y in points]
        dl.line(points, fill=255, width=round((STROKE_MM*scale+LIP_MM*2)*ppm), joint="curve")
        for width, value in ((STROKE_MM, 55), (STROKE_MM*.70, 148), (STROKE_MM*.34, 255)):
            dc.line(points, fill=value, width=max(1, round(width*scale*ppm)), joint="curve")

    for col in range(-1, COLUMNS+1):
        cx = (col+.5)*cell_w
        for row in range(-1, ROWS+1):
            cy = (row+.5)*cell_h
            # One continuous slightly curved stem, shared by successive cells.
            stem = bezier((0, -cell_h/2), (.65, -2.5), (-.65, 2.5), (0, cell_h/2))
            stroke(stem, cx, cy, .75)
            for side in (-1, 1):
                for leaf in leaves:
                    stroke([(x*side, y) for x, y in leaf], cx, cy)
                stroke([(x*side, y) for x, y in vein], cx, cy, .53)
    cut = np.asarray(cut.resize((W, H), Image.Resampling.LANCZOS), dtype=np.float32)/255
    lip = np.asarray(lip.resize((W, H), Image.Resampling.LANCZOS), dtype=np.float32)/255
    return cut, np.clip(lip-cut*1.6, 0, 1)


def patches():
    cut, lip = pattern()
    rng = np.random.default_rng(SEED)
    tiny = rng.integers(0, 256, (180, 60), dtype=np.uint8)
    grain = (np.asarray(Image.fromarray(tiny).resize((W, H), Image.Resampling.BICUBIC), dtype=np.float32)-127.5)/127.5
    tone = 1 + grain*.018 - cut*.48 + lip*.075
    base = np.rint(np.clip(tone[:, :, None]*np.asarray(GOLD_RGB, dtype=np.float32), 0, 255)).astype(np.uint8)
    orm = np.empty_like(base)
    orm[:, :, 0] = 255
    orm[:, :, 1] = np.rint(np.clip(.435+grain*.016+cut*.17-lip*.065, .33, .66)*255).astype(np.uint8)
    orm[:, :, 2] = np.rint((1-cut*.06)*255).astype(np.uint8)
    height = -cut*DEPTH_MM + grain*.0003
    dy, dx = np.gradient(height, AXIAL_MM/H, CIRCUMFERENCE_MM/W)
    nx, ny = np.clip(-dx, -.95, .95), np.clip(dy, -.95, .95)
    inv = 1/np.sqrt(nx*nx+ny*ny+1)
    gl = np.rint(np.clip(np.stack((nx*inv, ny*inv, inv), -1)*127+128, 0, 255)).astype(np.uint8)
    directx = gl.copy()
    directx[:, :, 1] = 255-directx[:, :, 1]
    return {"base": base, "orm": orm, "gl": gl, "dx": directx}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup():
    manifest_path = BACKUP / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for filename, checksum in manifest.items():
            if file_hash(BACKUP/filename) != checksum:
                raise RuntimeError(f"Backup checksum mismatch: {filename}")
        return
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup: {BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for filename in FILES.values():
        shutil.copy2(TEXTURES/filename, BACKUP/filename)
        manifest[filename] = file_hash(TEXTURES/filename)
        assert manifest[filename] == file_hash(BACKUP/filename)
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")


def protected_hash(image):
    digest = hashlib.sha256()
    for box in ((0, 0, 3584, 4096), (3584, 2048, 4096, 4096)):
        digest.update(image.crop(box).tobytes())
    return digest.hexdigest()


def main():
    backup()
    generated, temporary, preservation = patches(), [], {}
    try:
        for key, filename in FILES.items():
            with Image.open(TEXTURES/filename) as source:
                if source.size != (4096, 4096) or source.mode not in ("RGB", "RGBA"):
                    raise ValueError(f"Unexpected atlas format: {filename}")
                image = source.copy()
            before = protected_hash(image)
            patch = Image.fromarray(generated[key])
            if image.mode == "RGBA":
                patch = patch.convert("RGBA")
                patch.putalpha(image.crop(BOX).getchannel("A"))
            image.paste(patch, BOX)
            after = protected_hash(image)
            assert before == after
            preservation[filename] = {"before_sha256": before, "after_sha256": after, "unchanged": True}
            path = TEXTURES/(filename+".connected-tmp.png")
            image.save(path, compress_level=3)
            temporary.append((path, TEXTURES/filename))
            del image
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for path, _ in temporary:
            path.unlink(missing_ok=True)
    report = {"status": "connected socket engraving generated", "backup": str(BACKUP),
              "region": list(BOX), "columns_rows": [COLUMNS, ROWS],
              "motif_size_mm": [CIRCUMFERENCE_MM/COLUMNS, AXIAL_MM/ROWS],
              "cut_width_mm": STROKE_MM, "depth_mm": DEPTH_MM, "lip_width_mm": LIP_MM,
              "orm_alpha_preserved": True, "protected_pixels": preservation}
    (OUT/"Connected_Socket_Verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
