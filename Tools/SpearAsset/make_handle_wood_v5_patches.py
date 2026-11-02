"""Generate standalone wood candidates; NEVER write a production atlas.

The accepted spearhead and all current atlas files are read-only inputs. Output
is restricted to Saved/Diagnostics/ImperialSpear/HandleFinish/patches/wood_v5.
V5 REQUIRES four axial shaft UV strips. It is not compatible with older UVs.
The rounded physical height field drives normals, roughness and quiet albedo;
long white highlights must come from lighting, not painted light/dark stripes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
TEXTURES = ROOT / "Exports/ImperialSpear/Textures"
OUTPUT = ROOT / "Saved/Diagnostics/ImperialSpear/HandleFinish/patches/wood_v5"
REGION = (0, 2048, 2048, 4096)
W, H = 496, 8128
TILE = 2048
STRIP_COUNT, STRIP_H = 4, 2032
CELL_W, CELL_H, GUTTER = 512, 2048, 8
SEED = 27102731
BASE_RGB = (57, 29, 27)
RIBS = 54
RIB_FWHM_MM = (.30, 1.30)
RIB_HEIGHT_MM = (.080, .190)
ROUGHNESS_RANGE = (.40, .66)
HEIGHT_GAIN = 1.0
FINE_FIBRES = 420
HEIGHT_ENCODING_MM = (-.14, .28)
FILES = {
    "BaseColor": "T_ImperialSpear_BaseColor.png",
    "ORM": "T_ImperialSpear_ORM.png",
    "NormalGL": "T_ImperialSpear_NormalGL.png",
    "NormalDX": "T_ImperialSpear_NormalDX.png",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def field(rng, cells_x, cells_y):
    pixels = rng.integers(0, 256, (cells_y, cells_x), dtype=np.uint8)
    # Extend before filtering so the colour/roughness noise is periodic too.
    tiled = Image.fromarray(np.tile(pixels, (1, 3)))
    middle = tiled.resize((3*W, H), Image.Resampling.BICUBIC).crop((W, 0, 2*W, H))
    return (np.asarray(middle, dtype=np.float32)-127.5)/127.5


def pack_strips(values):
    """Losslessly pack native rows; X wraps and Y crosses slice boundaries."""
    assert values.shape[:2] == (H, W)
    result = np.empty((TILE, TILE)+values.shape[2:], dtype=values.dtype)
    columns = np.arange(-GUTTER, W+GUTTER) % W
    for strip in range(STRIP_COUNT):
        rows = np.clip(np.arange(strip*STRIP_H-GUTTER, (strip+1)*STRIP_H+GUTTER), 0, H-1)
        result[:, strip*CELL_W:(strip+1)*CELL_W] = values[rows][:, columns]
        assert np.array_equal(result[GUTTER:GUTTER+STRIP_H, strip*CELL_W+GUTTER:strip*CELL_W+GUTTER+W],
                              values[strip*STRIP_H:(strip+1)*STRIP_H])
    return result


def mapping_recipe(length_mm):
    rows = []
    for strip in range(STRIP_COUNT):
        x0, x1 = strip*CELL_W+GUTTER, strip*CELL_W+GUTTER+W
        y0, y1 = 2048+GUTTER, 2048+GUTTER+STRIP_H
        rows.append({"strip_index": strip, "source_z_top_m": 1.66-strip*length_mm/4000,
                     "source_z_bottom_m": 1.66-(strip+1)*length_mm/4000,
                     "atlas_pixel_box": [x0, y0, x1, y1],
                     "atlas_uv_bounds": [x0/4096, 1-y1/4096, x1/4096, 1-y0/4096]})
    return rows


def seam_errors(packed):
    """Bilinear samples exactly at U-wrap and axial-cut pixel boundaries."""
    pixels = packed.astype(np.float32)
    u_error, v_error = 0.0, 0.0
    for strip in range(STRIP_COUNT):
        x = strip*CELL_W
        left = (pixels[:, x+GUTTER-1]+pixels[:, x+GUTTER])*.5
        right = (pixels[:, x+GUTTER+W-1]+pixels[:, x+GUTTER+W])*.5
        u_error = max(u_error, float(np.max(np.abs(left-right))))
        if strip < STRIP_COUNT-1:
            upper = pixels[GUTTER+STRIP_H-1:GUTTER+STRIP_H+1, x+GUTTER:x+GUTTER+W].mean(axis=0)
            lower = pixels[GUTTER-1:GUTTER+1, x+CELL_W+GUTTER:x+CELL_W+GUTTER+W].mean(axis=0)
            v_error = max(v_error, float(np.max(np.abs(upper-lower))))
    assert u_error == 0 and v_error == 0, (u_error, v_error)
    return {"u_wrap_max_encoded_error": u_error, "axial_cut_max_encoded_error": v_error,
            "sample_method": "Bilinear boundary samples, all four U wraps and three axial cuts"}


def curved_bundle_grain(rng, circumference, length):
    """Coherent arcing bundles, split/rejoin lenses and small knot deflection.

    A shared low-frequency flow bends neighbouring fibres together. Individual
    tracks vary in width and fade; secondary tracks fork from and return to a
    parent, so the height field is a connected grain structure, not a comb.
    """
    height = np.zeros((H, W), dtype=np.float32)
    y = (np.arange(H, dtype=np.float32)+.5)*length/H
    gaps = np.clip(rng.lognormal(0, .50, RIBS), .42, 2.5)
    anchors = np.cumsum(gaps)/gaps.sum()*circumference

    def smooth_controls(values, span=(30, 95)):
        knots = [-160.0]
        while knots[-1] < length+160:
            knots.append(knots[-1]+rng.uniform(*span))
        knots = np.asarray(knots, dtype=np.float32)
        controls = rng.choice(values, len(knots))
        index = np.clip(np.searchsorted(knots, y)-1, 1, len(knots)-3)
        t = (y-knots[index])/(knots[index+1]-knots[index])
        a, b, c, d = (controls[index+offset] for offset in (-1, 0, 1, 2))
        return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)

    common = smooth_controls(np.linspace(-3.0, 3.0, 11), (25, 65))
    bundle_flows = [smooth_controls(np.linspace(-2.1, 2.1, 11), (25, 65)) for _ in range(9)]
    knots = [(rng.uniform(0, circumference), rng.uniform(40, length-40),
              rng.uniform(2.0, 4.0), rng.uniform(18, 35), rng.uniform(1.2, 2.3)) for _ in range(10)]
    tracks = []
    branch_count = 0

    def add_track(center, width, amplitude, rows=None):
        rows = np.arange(H) if rows is None else rows
        c, w, a = center[rows], width[rows], amplitude[rows]
        margin = float(w.max())*1.7
        left = math.floor((float(c.min())-margin)*W/circumference)
        right = math.ceil((float(c.max())+margin)*W/circumference)
        columns = np.arange(left, right+1)
        distance = (columns.astype(np.float32)+.5)*circumference/W-c[:, None]
        profile = np.exp(-.5*(distance/(w[:, None]/2.35482))**2)
        index = np.ix_(rows, columns % W)
        previous = height[index]
        height[index] = previous+a[:, None]*profile*(1-previous/.22)

    for rib in range(RIBS):
        anchor = anchors[rib]
        group = anchor/circumference*len(bundle_flows)
        index, blend = int(math.floor(group)) % len(bundle_flows), group % 1
        center = anchor+common+bundle_flows[index]*(1-blend)+bundle_flows[(index+1) % len(bundle_flows)]*blend
        center += smooth_controls(np.linspace(-.45, .45, 7), (20, 45))
        for xk, yk, xwidth, ywidth, amplitude in knots:
            distance = (anchor-xk+circumference*.5) % circumference-circumference*.5
            center += np.sign(distance)*amplitude*math.exp(-.5*(distance/xwidth)**2)*np.exp(-.5*((y-yk)/ywidth)**2)
        coverage = np.clip(smooth_controls((0, .12, .35, .7, 1, 1), (30, 95)), 0, 1)
        width_variation = np.clip(smooth_controls((.65, .85, 1, 1.15), (30, 90)), .55, 1.25)
        width = rng.uniform(*RIB_FWHM_MM)*width_variation*(.35+.65*np.sqrt(coverage))
        amplitude = rng.uniform(*RIB_HEIGHT_MM)*coverage
        add_track(center, width, amplitude)
        tracks.append(center.astype(np.float32))
        # Short tapered fibres leave the parent and rejoin it, forming narrow
        # growth lenses. They are sparse and unequal, not a repeating braid.
        for _ in range(int(rng.integers(1, 4))):
            start = rng.uniform(-20, length-35)
            span = rng.uniform(25, 85)
            t = np.clip((y-start)/span, 0, 1)
            envelope = np.maximum(0, np.sin(math.pi*t))**1.3
            branch = center+rng.choice((-1, 1))*rng.uniform(1.2, 3.5)*envelope
            branch_width = np.maximum(.12, width*rng.uniform(.35, .65)*(.2+.8*envelope))
            branch_height = np.maximum(amplitude, .045)*rng.uniform(.45, .80)*envelope
            rows = np.flatnonzero((y>start) & (y<start+span))
            if len(rows)>2:
                add_track(branch, branch_width, branch_height, rows)
                branch_count += 1
    metadata = {"split_rejoin_lenses": branch_count, "small_knot_deflections": len(knots),
                "shared_flow_lateral_excursion_mm": [3, 5], "shared_flow_axial_span_mm": [25, 65]}
    return height, tracks, metadata


def pore_and_fibre_masks(rng, circumference, length, tracks):
    fine_image, pores_image = Image.new("L", (W, H)), Image.new("L", (W, H))
    fine_draw, pore_draw = ImageDraw.Draw(fine_image), ImageDraw.Draw(pores_image)
    px, py = W/circumference, H/length
    for _ in range(FINE_FIBRES):
        y0 = rng.uniform(-100, length)
        span, width = rng.uniform(12, 130), rng.uniform(.22, .48)
        track = tracks[int(rng.integers(0, len(tracks)))]
        offset = rng.uniform(-.65, .65)
        samples = np.linspace(0, 1, 28)
        points = [(float(track[int(np.clip((y0+t*span)/length*H, 0, H-1))])+offset, y0+t*span) for t in samples]
        widths = [width*math.sin(math.pi*t)**.5 for t in samples]
        value = int(rng.integers(90, 220))
        for wrap in (-circumference, 0, circumference):
            left = [((xx+wrap-ww*.5)*px, yy*py) for (xx, yy), ww in zip(points, widths)]
            right = [((xx+wrap+ww*.5)*px, yy*py) for (xx, yy), ww in zip(points, widths)]
            fine_draw.polygon(left+list(reversed(right)), fill=value)
    for _ in range(1050):
        x, y = rng.uniform(0, circumference), rng.uniform(-8, length)
        width = rng.uniform(.30, .65)
        span = float(np.clip(rng.lognormal(math.log(3.8), .55), 1.5, 12))
        row = int(np.clip(y/length*H, 0, H-1))
        track = min(tracks, key=lambda path: abs((float(path[row])-x+circumference*.5) % circumference-circumference*.5))
        offset = (x-float(track[row])+circumference*.5) % circumference-circumference*.5
        samples = np.linspace(0, 1, 12)
        points = [(float(track[int(np.clip((y+t*span)/length*H, 0, H-1))])+offset, y+t*span) for t in samples]
        widths = [width*math.sin(math.pi*t)**.65 for t in samples]
        value = int(rng.integers(80, 240))
        for wrap in (-circumference, 0, circumference):
            left = [((xx+wrap-ww*.5)*px, yy*py) for (xx, yy), ww in zip(points, widths)]
            right = [((xx+wrap+ww*.5)*px, yy*py) for (xx, yy), ww in zip(points, widths)]
            pore_draw.polygon(left+list(reversed(right)), fill=value)
    convert = lambda image, blur: np.asarray(image.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32)/255
    return convert(fine_image, .45), convert(pores_image, .45)


def cross_scratches(rng, circumference, length):
    """Sparse shallow cuts, integrated across the anisotropic axial texel."""
    height = np.zeros((H, W), dtype=np.float32)
    sx, sy = circumference/W, length/H
    for _ in range(150):
        x, y = rng.uniform(0, circumference), rng.uniform(0, length)
        span = rng.uniform(1.8, 7.5)
        slope = rng.uniform(-.65, .65)
        sigma = rng.uniform(.10, .22)
        filtered_sigma = math.sqrt(sigma*sigma+sy*sy/12)
        amplitude = rng.uniform(.025, .065)*sigma/filtered_sigma
        cols = np.arange(math.floor((x-span*.6)/sx), math.ceil((x+span*.6)/sx)+1)
        margin = abs(slope)*span*.6+filtered_sigma*3.5
        rows = np.arange(max(0, math.floor((y-margin)/sy)), min(H, math.ceil((y+margin)/sy)+1))
        xx = (cols.astype(np.float32)+.5)*sx-x
        yy = (rows.astype(np.float32)+.5)*sy-y
        distance = (yy[:, None]-slope*xx[None, :])/math.sqrt(1+slope*slope)
        taper = np.clip(1-(xx/(span*.55))**2, 0, 1)**.7
        mask = np.exp(-.5*(distance/filtered_sigma)**2)*taper[None, :]
        height[np.ix_(rows, cols % W)] += amplitude*mask
    return height


def shallow_dents(rng, circumference, length):
    image = Image.new("L", (W, H)); draw = ImageDraw.Draw(image)
    for _ in range(75):
        x, y = rng.uniform(0, circumference), rng.uniform(0, length)
        radius_x, radius_y = rng.uniform(.35, .9), rng.uniform(.5, 1.6)
        value = int(rng.integers(75, 210))
        for wrap in (-circumference, 0, circumference):
            draw.ellipse(((x+wrap-radius_x)*W/circumference, (y-radius_y)*H/length,
                          (x+wrap+radius_x)*W/circumference, (y+radius_y)*H/length), fill=value)
    return np.asarray(image.filter(ImageFilter.GaussianBlur(.8)), dtype=np.float32)/255


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circumference-mm", type=float, default=100.0)
    parser.add_argument("--axial-mm", type=float, default=1570.0)
    parser.add_argument("--roughness", type=float, default=.60)
    parser.add_argument("--specular", type=float, default=.37)
    args = parser.parse_args()
    assert 50 <= args.circumference_mm <= 200 and 500 <= args.axial_mm <= 3000
    assert .40 <= args.roughness <= .60 and .30 <= args.specular <= .50
    started = time.perf_counter()
    source_hashes = {name: sha256(TEXTURES/name) for name in FILES.values()}
    original = {}
    for key, name in FILES.items():
        with Image.open(TEXTURES/name) as image:
            assert image.size == (4096, 4096) and image.mode in ("RGB", "RGBA"), name
            original[key] = np.array(image.crop(REGION))
    assert original["ORM"].shape[2] == 4, "ORM must contain packed specular alpha"
    rng = np.random.default_rng(SEED)
    ribs, tracks, grain_metadata = curved_bundle_grain(rng, args.circumference_mm, args.axial_mm)
    fibres, pores = pore_and_fibre_masks(rng, args.circumference_mm, args.axial_mm, tracks)
    scratches = cross_scratches(rng, args.circumference_mm, args.axial_mm)
    dents = shallow_dents(rng, args.circumference_mm, args.axial_mm)
    cuts = pores*.085+scratches*(1-pores*.85)
    cuts += dents*.060*(1-np.clip(cuts/.11, 0, 1))
    height = (ribs+fibres*.030-cuts)*HEIGHT_GAIN
    assert np.isfinite(height).all()
    assert HEIGHT_ENCODING_MM[0] < float(height.min()) and float(height.max()) < HEIGHT_ENCODING_MM[1]
    crest = np.clip(ribs/.16, 0, 1)
    bundles, fine = field(rng, 45, 12), field(rng, 210, 65)
    grain_color = np.clip((ribs-.045)/.045, -1, 1)
    tone = 1+grain_color*.115+bundles*.025+fine*.010-pores*.130-np.clip(scratches/.04, 0, 1)*.110-dents*.065
    tone /= float(tone.mean())
    # Correlated wood colour retains readable grain on the shaded side. No
    # painted silver highlights: glints still follow the rounded physical field.
    color = tone[:, :, None]*np.asarray(BASE_RGB, dtype=np.float32)
    color[:, :, 0] += bundles*1.8
    color[:, :, 1] -= bundles*.6
    result = {key: pixels.copy() for key, pixels in original.items()}
    result["BaseColor"][:, :, :3] = pack_strips(np.rint(np.clip(color, 0, 255)).astype(np.uint8))
    # The wide rough valleys must not blur away the separate polished fibre
    # highlights. This mask follows the raised runs, including their tapers.
    polished = np.maximum(np.clip((ribs-.002)/.040, 0, 1)**.35,
                          np.sqrt(fibres)*.9)
    roughness = np.clip(args.roughness-polished*.180+pores*.060+bundles*.010+fine*.012
                        +np.clip(scratches/.04, 0, 1)*.045,
                        *ROUGHNESS_RANGE)
    specular = np.clip(args.specular+polished*.003-pores*.008, .35, .38)
    result["ORM"][:, :, 1] = pack_strips(np.rint(roughness*255).astype(np.uint8))
    result["ORM"][:, :, 3] = pack_strips(np.rint(specular*255).astype(np.uint8))
    # Derive normals in the continuous native physical domain BEFORE packing.
    # X is periodic; PNG rows oppose V. Slice boundaries cannot alter normals.
    dx = (np.roll(height, -1, axis=1)-np.roll(height, 1, axis=1))/(2*args.circumference_mm/W)
    dy = np.gradient(height, args.axial_mm/H, axis=0)
    nx, ny = -dx, dy
    inv = 1/np.sqrt(nx*nx+ny*ny+1)
    normal = np.rint(np.clip((np.stack((nx*inv, ny*inv, inv), axis=-1)+1)*127.5, 0, 255)).astype(np.uint8)
    packed_normal = pack_strips(normal)
    result["NormalGL"][:, :, :3] = packed_normal
    result["NormalDX"][:, :, :3] = packed_normal
    result["NormalDX"][:, :, 1] = 255-packed_normal[:, :, 1]
    assert np.array_equal(result["ORM"][:, :, [0, 2]], original["ORM"][:, :, [0, 2]])
    continuity = {key: seam_errors(pixels) for key, pixels in result.items()}
    normal_lengths = np.linalg.norm(normal.astype(np.float32)/127.5-1, axis=-1)
    normal_quality = {"length_min_max": [float(normal_lengths.min()), float(normal_lengths.max())],
                      "maximum_unit_length_error": float(np.max(np.abs(normal_lengths-1))),
                      "directx_green_exact_inverse": bool(np.array_equal(result["NormalDX"][:, :, 1], 255-result["NormalGL"][:, :, 1]))}
    assert normal_quality["maximum_unit_length_error"] < .007 and normal_quality["directx_green_exact_inverse"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for key, pixels in result.items():
        path = OUTPUT/("Wood_"+key+".png")
        Image.fromarray(pixels).save(path, compress_level=3)
        outputs[key] = {"path": str(path), "sha256": sha256(path)}
    encoded = np.rint((height-HEIGHT_ENCODING_MM[0])/(HEIGHT_ENCODING_MM[1]-HEIGHT_ENCODING_MM[0])*65535).astype(np.uint16)
    height_path = OUTPUT/"Wood_Height16.png"
    packed_height = pack_strips(encoded)
    continuity["Height16"] = seam_errors(packed_height)
    Image.fromarray(packed_height).save(height_path, compress_level=3)
    Image.fromarray(encoded).save(OUTPUT/"Wood_Height16_Native.png", compress_level=3)
    outputs["Height16"] = {"path": str(height_path), "sha256": sha256(height_path),
                           "decode_mm": "-0.14 + (uint16/65535)*0.42"}
    # A physical-proportion height inspection (100x200 mm near the upper
    # handle), not a shaded material preview or an added production map.
    lo = int(40/args.axial_mm*H)
    hi = int(240/args.axial_mm*H)
    height_preview = Image.fromarray((encoded/257).astype(np.uint8)).crop((0, lo, W, hi))
    height_preview.resize((500, 1000), Image.Resampling.BILINEAR).save(OUTPUT/"Wood_Flow_HeightPreview.png")
    after_hashes = {name: sha256(TEXTURES/name) for name in FILES.values()}
    assert source_hashes == after_hashes, "Production atlas changed during patch generation"
    slope = np.sqrt(dx*dx+dy*dy)
    report = {"status": "STANDALONE V5 PATCHES; REQUIRE FOUR-STRIP SHAFT UV REMAP; NOT APPLIED OR RENDER-VALIDATED",
              "region": list(REGION), "patch_size": [TILE, TILE], "seed": SEED,
              "circumference_mm": args.circumference_mm, "axial_mm": args.axial_mm,
              "physical_texel_mm": [args.circumference_mm/W, args.axial_mm/H],
              "native_size_px": [W, H], "strip_count": STRIP_COUNT,
              "strip_native_size_px": [W, STRIP_H], "strip_cell_size_px": [CELL_W, CELL_H],
              "gutter_px": GUTTER, "strip_length_mm": args.axial_mm/STRIP_COUNT,
              "source_z_top_m": 1.66, "source_z_bottom_m": 1.66-args.axial_mm/1000,
              "uv_mapping": mapping_recipe(args.axial_mm),
              "uv_formula": "s=(1.66-z)*1000 mm; j=min(3,floor(s/392.5)); t=(s-j*392.5)/392.5; u=(j*512+8+496*angle_fraction)/4096; v=1-(2048+8+2032*t)/4096. Split geometry at z=1.2675,.875,.4825; separate corner UVs at slice borders.",
              "gutter_mode": "8px periodic circumference; neighboring native axial rows across strip borders; clamp only at shaft ends",
              "native_to_packed_interiors_lossless": True,
              "packed_map_continuity": continuity, "normal_quality": normal_quality,
              "normal_generation": "Continuous native physical height gradient before packing; unit-normalized",
              "height_preview_physical_size_mm": [100, 200], "height_preview_size_px": [500, 1000],
              "rounded_rib_count": RIBS, "rib_fwhm_mm": list(RIB_FWHM_MM),
              "rib_spacing": "Unequal coherent curved bundles, tapered split/rejoin lenses and local deflections",
              **grain_metadata,
              "axial_fibre_variation_span_mm": [30, 95],
              "pore_width_mm": [.30, .65], "pore_count": 1050,
              "cross_check_count": 150,
              "shallow_dent_count": 75,
              "height_gain": HEIGHT_GAIN, "fine_fibre_count": FINE_FIBRES,
              "fine_fibre_width_mm": [.22, .48], "fine_fibre_run_mm": [12, 130],
              "polished_crest_mask_mean": float(polished.mean()),
              "roughness_behavior": "Polished curved grain ~.42-.48; unpolished valleys ~.58-.61",
              "correlated_grain_albedo_contrast": .115,
              "pore_check_albedo_darkening": [.13, .11],
              "rib_height_mm": list(RIB_HEIGHT_MM), "base_rgb": list(BASE_RGB),
              "height_min_max_mm": [float(height.min()), float(height.max())],
              "height_peak_to_valley_mm": float(np.ptp(height)),
              "slope_percentiles_50_90_99_max": np.percentile(slope, [50, 90, 99, 100]).tolist(),
              "roughness_min_mean_max": [float(roughness.min()), float(roughness.mean()), float(roughness.max())],
              "specular_min_mean_max": [float(specular.min()), float(specular.mean()), float(specular.max())],
              "wood_ao_and_metallic_preserved": True,
              "production_atlases_byte_unchanged": source_hashes == after_hashes,
              "accepted_spearhead_pixels_untouched": True,
              "source_file_sha256": source_hashes, "outputs": outputs,
              "elapsed_seconds": time.perf_counter()-started}
    (OUTPUT/"Wood_Patch_Report.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
