import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
REFERENCE_SCRIPT = PROJECT / "Docs" / "PainterlyShaders" / "painterly_portfolio.py"

spec = importlib.util.spec_from_file_location("painterly_portfolio", REFERENCE_SCRIPT)
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)


def foreground_mask(guide_rgb, alpha):
    mx = np.max(guide_rgb, axis=-1)
    return (alpha > 0.02) & (mx >= 0.10)


def make_rainbow_diagonal_stripes(guide_rgb, alpha, stripe_px=74):
    h, w = guide_rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    band = np.floor((xx + yy) / max(float(stripe_px), 1.0)).astype(np.int32)
    palette = np.array(
        [
            [1.00, 0.00, 0.00],
            [1.00, 0.35, 0.00],
            [1.00, 0.95, 0.00],
            [0.10, 1.00, 0.00],
            [0.00, 0.95, 0.65],
            [0.00, 0.35, 1.00],
            [0.34, 0.00, 1.00],
            [1.00, 0.00, 0.85],
        ],
        dtype=np.float32,
    )
    rgb = palette[band % len(palette)]
    rgb = np.where(foreground_mask(guide_rgb, alpha)[..., None], rgb, 0.0)
    return rgb.astype(np.float32)


def quantize_color_for_preview(rgb, h_levels=24, s_levels=8, v_levels=8, blend=0.0):
    if blend <= 0:
        return rgb
    return pp.quantize_hsv(rgb, h_levels=h_levels, s_levels=s_levels, v_levels=v_levels, blend=blend)


def guided_oil_mode_filter(
    guide_rgb,
    color_rgb,
    alpha,
    radius,
    h_bins,
    v_bins,
    sat_floor,
    edge_strength=0.0,
    quantize_blend=0.0,
):
    guide_hsv = pp.rgb_to_hsv(np.clip(guide_rgb, 0.0, 1.0))
    hbin = np.floor(guide_hsv[..., 0] * h_bins).astype(np.int32) % h_bins
    vbin = np.clip(np.floor(guide_hsv[..., 2] * v_bins).astype(np.int32), 0, v_bins - 1)
    low_sat = guide_hsv[..., 1] < sat_floor
    key = hbin + h_bins * vbin
    key = np.where(low_sat, h_bins * v_bins + vbin, key)
    n_bins = h_bins * v_bins + v_bins

    best_count = np.full(guide_rgb.shape[:2], -1.0, dtype=np.float32)
    best_rgb = color_rgb.copy()
    fg = foreground_mask(guide_rgb, alpha).astype(np.float32)

    for k in range(n_bins):
        mask = ((key == k).astype(np.float32)) * fg
        if float(mask.mean()) < 0.00001:
            continue
        count = pp.box_blur_float(mask, radius)
        sums = []
        for c in range(3):
            sums.append(pp.box_blur_float(color_rgb[..., c] * mask, radius))
        avg = np.stack(sums, axis=-1) / np.maximum(count[..., None], 1e-5)
        take = count > best_count
        best_count = np.where(take, count, best_count)
        best_rgb = np.where(take[..., None], avg, best_rgb)

    out = quantize_color_for_preview(best_rgb, h_levels=max(8, h_bins), s_levels=8, v_levels=max(5, v_bins + 3), blend=quantize_blend)
    if edge_strength > 0:
        out *= 1.0 - edge_strength * pp.edge_mask(guide_rgb, sigma=0.8, strength=6.0)[..., None]
    out = np.where(foreground_mask(guide_rgb, alpha)[..., None], out, color_rgb)
    return np.clip(out, 0.0, 1.0)


def flow_smooth_signal_with_guide(signal_rgb, guide_rgb, length, samples, tensor_sigma, iterations):
    h, w = signal_rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    angle = pp.structure_tensor_angle(guide_rgb, tensor_sigma)
    vx = np.cos(angle).astype(np.float32)
    vy = np.sin(angle).astype(np.float32)
    out = signal_rgb.copy()
    half = max(1, samples // 2)
    for _ in range(iterations):
        accum = out.copy() * 1.2
        weight_sum = np.full((h, w, 1), 1.2, dtype=np.float32)
        for i in range(1, half + 1):
            dist = length * i / half
            weight = math.exp(-0.5 * (i / max(half * 0.62, 1e-5)) ** 2)
            accum += pp.bilinear_sample(out, xx + vx * dist, yy + vy * dist) * weight
            accum += pp.bilinear_sample(out, xx - vx * dist, yy - vy * dist) * weight
            weight_sum += 2.0 * weight
        out = accum / weight_sum
    return np.clip(out, 0.0, 1.0)


def guided_oil_reference_mid(guide_rgb, color_rgb, alpha, scale, edge_strength=0.0):
    return guided_oil_mode_filter(
        guide_rgb,
        color_rgb,
        alpha,
        radius=16.0 * scale,
        h_bins=16,
        v_bins=5,
        sat_floor=0.09,
        edge_strength=edge_strength,
        quantize_blend=0.0,
    )


def guided_hybrid_flow_oil_chunky_canvas(guide_rgb, color_rgb, alpha, scale, edge_strength=0.0):
    flow_length = 21.0 * scale
    oil_radius = 20.0 * scale
    guide_flowed = flow_smooth_signal_with_guide(
        guide_rgb,
        guide_rgb,
        length=flow_length,
        samples=9,
        tensor_sigma=max(2.0, flow_length * 0.35),
        iterations=2,
    )
    color_flowed = flow_smooth_signal_with_guide(
        color_rgb,
        guide_rgb,
        length=flow_length,
        samples=9,
        tensor_sigma=max(2.0, flow_length * 0.35),
        iterations=2,
    )
    return guided_oil_mode_filter(
        guide_flowed,
        color_flowed,
        alpha,
        radius=oil_radius,
        h_bins=10,
        v_bins=4,
        sat_floor=0.10,
        edge_strength=edge_strength,
        quantize_blend=0.0,
    )


def make_sheet(items, out_path, max_h=720):
    thumbs = []
    for label, path in items:
        im = Image.open(path).convert("RGB")
        if im.height > max_h:
            scale = max_h / im.height
            im = im.resize((max(1, int(round(im.width * scale))), max_h), Image.Resampling.LANCZOS)
        thumbs.append((label, im))

    pad = 14
    label_h = 28
    cols = len(thumbs)
    cell_w = max(im.width for _, im in thumbs)
    cell_h = max(im.height for _, im in thumbs)
    sheet = Image.new("RGB", (pad + cols * (cell_w + pad), pad + cell_h + label_h + pad), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(thumbs):
        x = pad + i * (cell_w + pad)
        y = pad
        draw.text((x, y), label, fill=(238, 238, 238))
        sheet.paste(im, (x, y + label_h))
    sheet.save(out_path, quality=95)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", default=r"C:\Users\singerie\Documents\Cursor\paint\hehe.EXR")
    parser.add_argument("--out", default=str(PROJECT / "Saved" / "guided_rainbow_repaint"))
    parser.add_argument("--max-size", type=int, default=0)
    parser.add_argument("--stripe-px", type=int, default=74)
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    guide_rgb, alpha = pp.load_image(Path(args.guide), max_size=args.max_size)
    scale = max(guide_rgb.shape[:2]) / 896.0
    rainbow = make_rainbow_diagonal_stripes(guide_rgb, alpha, stripe_px=max(1, int(round(args.stripe_px * scale))))

    original_path = out_dir / "00_normal_guide_original.png"
    rainbow_path = out_dir / "01_rainbow_diagonal_stripes_sharp.png"
    oil_path = out_dir / "02_guided_06_oil_hv_mode_reference_mid_rainbow_avg_strict.png"
    hybrid_path = out_dir / "03_guided_11_hybrid_flow_oil_chunky_canvas_rainbow_avg_strict.png"
    oil_edge_path = out_dir / "04_guided_06_oil_hv_mode_reference_mid_rainbow_avg_with_edges.png"
    hybrid_edge_path = out_dir / "05_guided_11_hybrid_flow_oil_chunky_canvas_rainbow_avg_with_edges.png"

    pp.save_png(original_path, guide_rgb, alpha)
    pp.save_png(rainbow_path, rainbow, alpha)

    oil = guided_oil_reference_mid(guide_rgb, rainbow, alpha, scale, edge_strength=0.0)
    hybrid = guided_hybrid_flow_oil_chunky_canvas(guide_rgb, rainbow, alpha, scale, edge_strength=0.0)
    oil_edge = guided_oil_reference_mid(guide_rgb, rainbow, alpha, scale, edge_strength=0.035)
    hybrid_edge = guided_hybrid_flow_oil_chunky_canvas(guide_rgb, rainbow, alpha, scale, edge_strength=0.055)
    pp.save_png(oil_path, oil, alpha)
    pp.save_png(hybrid_path, hybrid, alpha)
    pp.save_png(oil_edge_path, oil_edge, alpha)
    pp.save_png(hybrid_edge_path, hybrid_edge, alpha)

    sheet_path = out_dir / "guided_rainbow_repaint_sheet.png"
    make_sheet(
        [
            ("Normal guide", original_path),
            ("Sharp rainbow source", rainbow_path),
            ("#06 strict avg", oil_path),
            ("#11 strict avg", hybrid_path),
            ("#06 avg + guide edges", oil_edge_path),
            ("#11 avg + guide edges", hybrid_edge_path),
        ],
        sheet_path,
    )

    metadata = {
        "guide": str(args.guide),
        "scale": scale,
        "stripe_px_scaled": max(1, int(round(args.stripe_px * scale))),
        "outputs": {
            "normal_guide": str(original_path),
            "rainbow_source": str(rainbow_path),
            "oil_reference_mid_strict": str(oil_path),
            "hybrid_flow_oil_chunky_canvas_strict": str(hybrid_path),
            "oil_reference_mid_with_edges": str(oil_edge_path),
            "hybrid_flow_oil_chunky_canvas_with_edges": str(hybrid_edge_path),
            "sheet": str(sheet_path),
        },
    }
    (out_dir / "guided_rainbow_repaint_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(sheet_path)


if __name__ == "__main__":
    main()
