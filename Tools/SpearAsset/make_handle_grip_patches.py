"""Author independent handle PBR patches; never writes an existing atlas.

Run with the bundled workspace Python, Pillow and NumPy. The required JSON
configuration supplies measured physical dimensions and the agreed atlas boxes.
UV assignment and live Blender changes belong to the parent task.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish/patches'
SUFFIXES = ("BaseColor", "ORM", "NormalGL", "NormalDX")
SEED = 27102732


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cloud(rng, w, h, gx, gy):
    """Low-frequency random field periodic in circumference."""
    grid = rng.integers(0, 256, (gy, gx), dtype=np.uint8)
    repeated = np.tile(grid, (1, 3))
    large = Image.fromarray(repeated).resize((w*3, h), Image.Resampling.BICUBIC)
    field = np.asarray(large.crop((w, 0, 2*w, h)), dtype=np.float32)
    field = (field-field.mean())/max(float(field.std()), 1e-6)
    return np.clip(field, -2.5, 2.5)


def smooth_noise(rng, w, h, radius):
    noise = rng.integers(0, 256, (h, w), dtype=np.uint8)
    pad = max(5, math.ceil(radius*3))
    padded = np.pad(noise, ((0, 0), (pad, pad)), mode="wrap")
    image = Image.fromarray(padded).filter(ImageFilter.GaussianBlur(radius))
    result = np.asarray(image, dtype=np.float32)[:, pad:-pad]
    result = (result-result.mean())/max(float(result.std()), 1e-6)
    return np.clip(result, -3, 3)


def add_cut(height, mask, p0, p1, sigma, depth, width_mm, length_mm, section="gaussian"):
    """Metric soft V-score, bounded to a small segment box."""
    h, w = height.shape
    x0, y0 = p0; x1, y1 = p1
    support = sigma*3.4
    for offset in (-width_mm, 0, width_mm):
        a = np.array((x0+offset, y0), dtype=np.float32)
        b = np.array((x1+offset, y1), dtype=np.float32)
        ix0 = max(0, math.floor((min(a[0], b[0])-support)/width_mm*(w-1)))
        ix1 = min(w, math.ceil((max(a[0], b[0])+support)/width_mm*(w-1))+1)
        iy0 = max(0, math.floor((min(a[1], b[1])-support)/length_mm*(h-1)))
        iy1 = min(h, math.ceil((max(a[1], b[1])+support)/length_mm*(h-1))+1)
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        x = np.arange(ix0, ix1, dtype=np.float32)[None, :]*width_mm/(w-1)
        y = np.arange(iy0, iy1, dtype=np.float32)[:, None]*length_mm/(h-1)
        v = b-a
        t = np.clip(((x-a[0])*v[0]+(y-a[1])*v[1])/max(float(v@v), 1e-12), 0, 1)
        dist = np.hypot(x-a[0]-t*v[0], y-a[1]-t*v[1])
        # Keep gold's existing rounded chasing unchanged. Leather uses a
        # straight-sided incised section, with no raised quilted panel.
        cut = np.clip(1-dist/sigma, 0, 1) if section == "straight_v" else np.exp(-.5*(dist/sigma)**2)
        sl = np.s_[iy0:iy1, ix0:ix1]
        height[sl] = np.minimum(height[sl], -depth*cut)
        mask[sl] = np.maximum(mask[sl], cut)


def polyline(height, mask, points, sigma, depth, width_mm, length_mm, section="gaussian"):
    for a, b in zip(points, points[1:]):
        add_cut(height, mask, a, b, sigma, depth, width_mm, length_mm, section)


def cubic(a, b, c, d, count=8):
    a, b, c, d = map(lambda p: np.asarray(p, dtype=np.float32), (a, b, c, d))
    return [(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
            for t in np.linspace(0, 1, count+1)]


def leather_pores(rng, w, h, width_mm, length_mm):
    """Discrete irregular leather pits large enough to survive the game mip."""
    image = Image.new("L", (w, h))
    draw = ImageDraw.Draw(image)
    px, py = (w-1)/width_mm, (h-1)/length_mm
    for _ in range(round(width_mm*length_mm*1.85)):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        radius = rng.triangular(.045, .085, .19)
        rx, ry = radius*px, radius*py*rng.uniform(.7, 1.5)
        shade = int(rng.integers(105, 245))
        for wrap in (-w, 0, w):
            xx = x+wrap
            if xx+rx < 0 or xx-rx >= w:
                continue
            if rng.random() < .65:
                draw.ellipse((xx-rx, y-ry, xx+rx, y+ry), fill=shade)
            else:
                draw.polygon(((xx-rx, y-ry*.5), (xx+rx*.45, y-ry),
                              (xx+rx, y+ry*.4), (xx-rx*.2, y+ry)), fill=shade)
    return np.asarray(image.filter(ImageFilter.GaussianBlur(.34)), dtype=np.float32)/255


def leather_scores(w, h, width_mm, length_mm, rng):
    cut = np.zeros((h, w), dtype=np.float32)
    mask = np.zeros_like(cut)
    cell_w = width_mm/2
    cell_h = length_mm/4
    junctions = set()
    # Two lozenges around the wrap, four along its measured length. Slightly
    # bowed sides and clipped corner turns reproduce the broad scored loops.
    for row in range(-1, 10):
        cy = (row-.15)*cell_h*.5
        shift = .5*(row % 2)
        for col in range(-1, 3):
            cx = (col+shift)*cell_w
            vertices = np.array(((cx, cy-cell_h*.5), (cx+cell_w*.5, cy),
                                 (cx, cy+cell_h*.5), (cx-cell_w*.5, cy)), dtype=float)
            for i in range(4):
                a, d = vertices[i], vertices[(i+1) % 4]
                junctions.add((round(float(a[0] % width_mm), 5), round(float(a[1]), 5)))
                direction = d-a
                normal = np.array((-direction[1], direction[0]))
                normal /= np.linalg.norm(normal)
                unit = direction/np.linalg.norm(direction)
                a, d = a+unit*1.65, d-unit*1.65
                direction = d-a
                points = cubic(a, a+direction*.32+normal*.35,
                               a+direction*.68+normal*.35, d)
                depth = .300*(.98+.02*math.sin(row*1.61+col*.7))
                polyline(cut, mask, points, .42, depth, width_mm, length_mm, "straight_v")
                # A finer adjacent witness score makes the subtle doubled
                # edge visible in the reference, without a broad black band.
                if i in (0, 2):
                    secondary = [p+normal*.70 for p in points]
                    polyline(cut, mask, secondary, .22, depth*.40, width_mm, length_mm, "straight_v")
    # Each intersection turns around a small scored loop, as in the reference,
    # instead of four diagonals terminating in a dark X or a quilted button.
    for cx, cy in sorted(junctions):
        points = [(cx,cy-1.85),(cx+.80,cy-.80),(cx+1.15,cy),
                  (cx+.80,cy+.80),(cx,cy+1.85),(cx-.80,cy+.80),
                  (cx-1.15,cy),(cx-.80,cy-.80),(cx,cy-1.85)]
        polyline(cut, mask, points, .38, .255, width_mm, length_mm, "straight_v")
    # Wear breaks the depth slightly, not the major pattern's precision.
    wear = .96+.035*cloud(rng, w, h, 22, 46)
    cut *= np.clip(wear, .85, 1.04)
    return cut, mask


def pebbled_grain(w, h, width_mm, length_mm):
    """Irregular rounded leather cells, not a painted crack network.

    Nine local jittered-site comparisons form a periodic nearest/second-site
    distance field. Its broad, smooth ramps give ~0.75 mm pebbled grain while
    keeping the valleys shallow and free of black outlines.
    """
    rng = np.random.default_rng(SEED+2047)
    cols, rows = round(width_mm/.75), round(length_mm/.75)
    sx, sy = width_mm/cols, length_mm/rows
    jitter_x = rng.uniform(-.28, .28, (rows, cols)).astype(np.float32)
    jitter_y = rng.uniform(-.28, .28, (rows, cols)).astype(np.float32)
    amplitudes = rng.uniform(.055, .085, (rows, cols)).astype(np.float32)
    x = np.linspace(0, width_mm, w, dtype=np.float32)[None, :]
    y = np.linspace(0, length_mm, h, dtype=np.float32)[:, None]
    ix, iy = np.floor(x/sx).astype(int), np.floor(y/sy).astype(int)
    first = np.full((h, w), np.inf, dtype=np.float32)
    second = first.copy()
    amplitude = np.zeros_like(first)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            gx, gy = ix+ox, iy+oy
            lookup_x, lookup_y = gx % cols, gy % rows
            cx = (gx+.5+jitter_x[lookup_y, lookup_x])*sx
            cy = (gy+.5+jitter_y[lookup_y, lookup_x])*sy
            distance = (x-cx)**2+(y-cy)**2
            closer = distance < first
            second = np.where(closer, first, np.minimum(second, distance))
            first = np.minimum(first, distance)
            amplitude = np.where(closer, amplitudes[lookup_y, lookup_x], amplitude)
    gap = np.sqrt(second)-np.sqrt(first)
    t = np.clip(gap/.27, 0, 1)
    t = t*t*(3-2*t)
    height = t*amplitude
    height -= float(height.mean())
    color = t-float(t.mean())
    color /= max(float(np.abs(color).max()), 1e-6)
    return height.astype(np.float32), color.astype(np.float32)


def leather(w, h, circumference_mm, length_mm):
    rng = np.random.default_rng(SEED)
    broad = cloud(rng, w, h, 11, 23)
    medium = cloud(rng, w, h, 63, 128)
    fine = smooth_noise(rng, w, h, .65)
    pore = leather_pores(rng, w, h, circumference_mm, length_mm)
    cut, mask = leather_scores(w, h, circumference_mm, length_mm, rng)
    lip = np.exp(-((mask-.18)/.12)**2)*(mask < .5)*(mask > .025)
    pebble, grain_color = pebbled_grain(w, h, circumference_mm, length_mm)
    wear_rng = np.random.default_rng(SEED+501)
    wear_field = cloud(wear_rng, w, h, 8, 18)+.22*cloud(wear_rng, w, h, 35, 70)
    rubbed = np.clip((wear_field-.55)/1.5, 0, 1)
    rubbed = rubbed*rubbed*(3-2*rubbed)
    stains = np.clip((cloud(wear_rng, w, h, 37, 80)-1.2)*.5, 0, 1)
    incision_zone = np.clip(mask*2+lip*.65, 0, 1)
    grain_strength = (1-rubbed*.70)*(1-incision_zone*.88)
    pore_strength = (1-rubbed*.45)*(1-incision_zone*.55)
    height = cut+pebble*grain_strength+medium*.004+fine*.0035-pore*.042*pore_strength+lip*.008
    # The score is primarily a normal/roughness feature. The sRGB base loses
    # at most 10.5% at its center. Broader wear mottling breaks the uniform
    # pebble appearance, while rubbed lips reveal clean straight cut walls.
    tone = (1+broad*.005+medium*.009+fine*.006-pore*.17*pore_strength
            -mask*.105+lip*.045+grain_color*.055*grain_strength-rubbed*.075-stains*.14)
    rgb = tone[:, :, None]*np.array((67, 34, 33), dtype=np.float32)
    rough = .86+broad*.010+medium*.014+fine*.008+pore*.018+mask*.02-lip*.055-grain_color*.012-rubbed*.022+stains*.016
    rough = np.clip(rough+.86-float(rough.mean()), .80, .93)
    ao = np.clip(1-mask*.035-pore*.035, .93, 1)
    orm = np.stack((ao, rough, np.zeros_like(rough), np.full_like(rough, .18)), axis=-1)
    return rgb, orm, height, {"base_rgb": [67, 34, 33], "score_depth_mm": .300,
                             "score_half_width_mm": .42, "score_section": "Straight-sided V incision",
                             "roughness_mean": float(rough.mean()),
                             "score_color_darkening_max": .105,
                             "discrete_pits_per_square_mm": 1.85, "pit_depth_mm": .042,
                             "pit_radius_mm": [.045, .19], "worn_score_lip_height_mm": .008,
                             "pebbled_grain_mean_cell_mm": .75, "pebbled_grain_height_mm": [.055, .085],
                             "pebbled_grain_color_variation_max": .055, "specular_ior_level": .18,
                             "rubbed_patch_grain_reduction_max": .70, "incision_zone_grain_reduction_max": .88,
                             "rubbed_area_mean": float(rubbed.mean()), "dark_wear_mask_mean": float(stains.mean()),
                             "pattern": "Crisp angular lozenges, small pointed crossing loops and fine witness scores; sparse rubbed wear patches"}


def keeper_gold(w, h, circumference_mm, length_mm):
    rng = np.random.default_rng(SEED+1)
    broad = cloud(rng, w, h, 23, 5)
    medium = cloud(rng, w, h, 97, 23)
    fine = smooth_noise(rng, w, h, .55)
    cut = np.zeros((h, w), dtype=np.float32)
    mask = np.zeros_like(cut)
    cell = circumference_mm/10
    # Crossing angular chasing: straight steps, a short shoulder and pointed
    # chevron returns. No leaves, raised wires or dark painted outlines.
    for i in range(-1, 12):
        x = i*cell
        for side in (-1, 1):
            points = [(x-cell*.48, length_mm*.16),
                      (x-cell*.22, length_mm*.32),
                      (x-cell*.22, length_mm*.43),
                      (x+cell*.22, length_mm*.65),
                      (x+cell*.22, length_mm*.76),
                      (x+cell*.48, length_mm*.90)]
            if side < 0:
                points = [(2*x-px, py) for px, py in points]
            polyline(cut, mask, points, .145, .045, circumference_mm, length_mm)
    wear = np.clip(.82+cloud(rng, w, h, 35, 8)*.11, .55, 1)
    cut *= wear
    hairline_height = np.zeros_like(cut)
    hairlines = np.zeros_like(cut)
    for _ in range(270):
        x, y = rng.uniform(0, circumference_mm), rng.uniform(0, length_mm)
        angle = rng.uniform(-math.pi, math.pi)
        length = rng.triangular(.35, 1.4, 5)
        end = (x+math.cos(angle)*length, y+math.sin(angle)*length)
        add_cut(hairline_height, hairlines, (x, y), end,
                rng.uniform(.035, .065), rng.uniform(.004, .012), circumference_mm, length_mm)
    yy = np.linspace(0, length_mm, h, dtype=np.float32)[:, None]
    edge = np.exp(-np.minimum(yy, length_mm-yy)/.48)
    patina = edge*np.clip(.48+cloud(rng, w, h, 51, 9)*.24, 0, 1)
    height = cut+hairline_height+medium*.0025+fine*.0007
    # Match the accepted plain gold's measured median, adding restrained wear.
    tone = 1+broad*.014+medium*.007+fine*.0015-mask*.022-hairlines*.022-patina*.06
    tone /= float(tone.mean())  # Preserve accepted gold's mean brightness.
    rgb = tone[:, :, None]*np.array((162, 127, 69), dtype=np.float32)
    rough = np.clip(.405+broad*.019+medium*.008+mask*.026+hairlines*.025+patina*.045, .33, .47)
    ao = np.clip(1-mask*.016-patina*.012, .965, 1)
    metallic = np.clip(1-np.maximum(broad-1, 0)*.012, .97, 1)
    orm = np.stack((ao, rough, metallic, np.full_like(rough, .5)), axis=-1)
    return rgb, orm, height, {"base_rgb": [162, 127, 69], "score_depth_mm": .045,
                             "score_sigma_mm": .145, "roughness_mean": float(rough.mean()),
                             "score_color_darkening_max": .022,
                             "hairline_wear_count": 270, "hairline_depth_mm": [.004, .012],
                             "edge_patina_width_mm": .48, "mean_gold_brightness_preserved": True,
                             "pattern": "Ten crossed angular chevrons around each keeper"}


def normals(height_mm, circumference_mm, length_mm):
    dy = np.gradient(height_mm, length_mm/(height_mm.shape[0]-1), axis=0)
    dx = (np.roll(height_mm, -1, axis=1)-np.roll(height_mm, 1, axis=1))/(2*circumference_mm/(height_mm.shape[1]-1))
    nx, ny = -dx, dy  # Raster Y decreases UV V.
    length = np.sqrt(nx*nx+ny*ny+1)
    gl = np.stack((nx/length, ny/length, 1/length), axis=-1)*.5+.5
    dxn = gl.copy(); dxn[:, :, 1] = 1-dxn[:, :, 1]
    return gl, dxn


def padded(array, gutter):
    if array.ndim == 2:
        return np.pad(array, ((gutter, gutter), (gutter, gutter)), mode="edge")
    return np.pad(array, ((gutter, gutter), (gutter, gutter), (0, 0)), mode="edge")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--only", choices=("Leather", "KeeperGold"), nargs="+")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    selected = set(args.only or ("Leather", "KeeperGold"))
    previous_path = OUT/"HandlePatchManifest.json"
    retained = {}
    if previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        retained = {name: value for name, value in previous["patches"].items() if name not in selected}
    atlas = ROOT/"Exports/ImperialSpear/Textures"
    before = {suffix: file_hash(atlas/f"T_ImperialSpear_{suffix}.png") for suffix in SUFFIXES}
    result = {"scope": "Independent patches only; existing atlases and Blender untouched", "patches": retained,
              "revision": config.get("revision", "Unversioned"), "regenerated_materials": sorted(selected),
              "atlas_sha256_before": before, "channel_layout": "ORM alpha: Specular IOR Level"}
    for name, fn in (("Leather", leather), ("KeeperGold", keeper_gold)):
        if name not in selected:
            continue
        settings = config[name]
        box = settings["atlas_pixel_box"]
        gutter = settings.get("gutter_px", 12)
        width, height = box[2]-box[0], box[3]-box[1]
        w, h = width-2*gutter, height-2*gutter
        assert w > 32 and h > 32
        circumference_mm = settings["circumference_m"]*1000
        length_mm = settings["axial_length_m"]*1000
        rgb, orm, relief, audit = fn(w, h, circumference_mm, length_mm)
        # First/last content texels represent the same cylindrical meridian.
        for a in (rgb, orm, relief):
            a[:, -1] = a[:, 0]
        gl, dx = normals(relief, circumference_mm, length_mm)
        for a in (gl, dx):
            a[:, -1] = a[:, 0]
        files = {}
        for suffix, array, scale in (("BaseColor", rgb, 1), ("ORM", orm, 255),
                                     ("NormalGL", gl, 255), ("NormalDX", dx, 255)):
            pixels = np.rint(np.clip(padded(array, gutter)*scale, 0, 255)).astype(np.uint8)
            path = OUT/f"{name}_{suffix}.png"
            Image.fromarray(pixels).save(path, compress_level=3)
            files[suffix] = {"filename": path.name, "sha256": file_hash(path),
                             "mode": "RGBA" if suffix == "ORM" else "RGB"}
        # Float source retains physically measured depth for inspection only.
        np.save(OUT/f"{name}_Height_mm.npy", padded(relief, gutter))
        uv = [(box[0]+gutter)/4096, 1-(box[3]-gutter)/4096,
              (box[2]-gutter)/4096, 1-(box[1]+gutter)/4096]
        result["patches"][name] = {**settings, "content_uv_bounds_umin_vmin_umax_vmax": uv,
                                  "size": [width, height], "files": files, **audit,
                                  "height_min_max_mm": [float(relief.min()), float(relief.max())],
                                  "physical_uv": "U around circumference; V rises along shaft Z",
                                  "circumference_seam_first_last_texels_identical": True}
        # Flat-lit normal preview is a diagnostic, not a painted texture.
        light = np.array((-.44, .42, .79)); light /= np.linalg.norm(light)
        normal = gl*2-1
        lit = np.clip(np.sum(normal*light, axis=-1)*.40+.60, .18, 1.2)
        preview = np.rint(np.clip(rgb*lit[:, :, None]*1.7, 0, 255)).astype(np.uint8)
        Image.fromarray(preview).save(OUT/f"{name}_Diagnostic.png", compress_level=3)
    after = {suffix: file_hash(atlas/f"T_ImperialSpear_{suffix}.png") for suffix in SUFFIXES}
    assert before == after, "Existing atlas changed during patch generation"
    result["atlas_sha256_after"] = after
    result["existing_atlas_files_unchanged"] = True
    (OUT/"HandlePatchManifest.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
