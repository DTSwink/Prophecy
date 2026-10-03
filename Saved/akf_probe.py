import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


EPSILON = 1e-5
TWO_PI = 6.28318530718
VARIANCE_SCALE = 64.0
FIXED_VARIANCE_SCALE = 384.0
SECTORS = 8


def run_text(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE)


def probe_size(path):
    out = run_text(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ]
    )
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"]), stream.get("pix_fmt", "")


def load_exr_rgba(path):
    width, height, pix_fmt = probe_size(path)
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba64le",
            "-",
        ],
        stderr=subprocess.PIPE,
    )
    arr = np.frombuffer(raw, dtype=np.uint16).reshape((height, width, 4))
    rgba = arr.astype(np.float32) / 65535.0
    return rgba[..., :3], rgba[..., 3], pix_fmt


def normalize(v):
    lens = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(lens > EPSILON, v / np.maximum(lens, EPSILON), np.array([0.0, 0.0, 1.0], dtype=np.float32))


def sample_rgb(img, positions):
    h, w, _ = img.shape
    p = np.asarray(positions, dtype=np.float32)
    x = np.clip(p[..., 0], 0.0, w - 1.0)
    y = np.clip(p[..., 1], 0.0, h - 1.0)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    tx = (x - x0)[..., None]
    ty = (y - y0)[..., None]

    c00 = img[y0, x0]
    c10 = img[y0, x1]
    c01 = img[y1, x0]
    c11 = img[y1, x1]
    return (c00 * (1.0 - tx) + c10 * tx) * (1.0 - ty) + (c01 * (1.0 - tx) + c11 * tx) * ty


def sample_normal(img, positions):
    return normalize(sample_rgb(img, positions) * 2.0 - 1.0)


def structure_tensor(img, positions):
    p = np.asarray(positions, dtype=np.float32)
    offsets = np.array(
        [
            [-1.0, -1.0],
            [-1.0, 0.0],
            [-1.0, 1.0],
            [1.0, -1.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, -1.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    s = sample_normal(img, p[:, None, :] + offsets[None, :, :])
    fx = (-s[:, 0] - 2.0 * s[:, 1] - s[:, 2] + s[:, 3] + 2.0 * s[:, 4] + s[:, 5]) * 0.25
    fy = (-s[:, 0] - 2.0 * s[:, 6] - s[:, 3] + s[:, 2] + 2.0 * s[:, 7] + s[:, 5]) * 0.25
    return np.stack([np.sum(fx * fx, axis=-1), np.sum(fx * fy, axis=-1), np.sum(fy * fy, axis=-1)], axis=-1)


def gaussian_tensor(img, pos, radius, stddev, tensor_offsets, tensor_weights):
    shifted = pos[None, :] + tensor_offsets
    tensors = structure_tensor(img, shifted)
    return np.sum(tensors * tensor_weights[:, None], axis=0) / max(float(np.sum(tensor_weights)), EPSILON)


def compute_eigen(img, pos, radius, stddev, tensor_offsets, tensor_weights):
    g = gaussian_tensor(img, pos, radius, stddev, tensor_offsets, tensor_weights)
    disc = math.sqrt(max((g[0] - g[2]) * (g[0] - g[2]) + 4.0 * g[1] * g[1], EPSILON))
    lambda1 = 0.5 * (g[0] + g[2] + disc)
    lambda2 = 0.5 * (g[0] + g[2] - disc)
    t = np.array([lambda1 - g[0], -g[1]], dtype=np.float32)
    t_len = float(np.linalg.norm(t))
    t = t / t_len if t_len > EPSILON else np.array([0.0, 1.0], dtype=np.float32)
    phi = math.atan2(float(t[1]), float(t[0]))
    anisotropy = np.clip((lambda1 - lambda2) / max(lambda1 + lambda2, EPSILON), 0.0, 1.0)
    return phi, float(anisotropy), g


def filter_pixel(img, pos, args, disk_offsets, tensor_offsets, tensor_weights):
    center_rgb = sample_rgb(img, pos[None, :])[0]
    if args.mode == "fixed" and (np.max(center_rgb) < 0.005 or np.min(center_rgb) > 0.995):
        center_n = normalize((center_rgb * 2.0 - 1.0)[None, :])[0]
        return {
            "encoded": center_rgb,
            "normal": center_n,
            "center_normal": center_n,
            "anisotropy": 0.0,
            "tensor": np.zeros(3, dtype=np.float32),
            "sector_weight_mean": 1.0,
            "sector_weight_min": 1.0,
            "sector_weight_max": 1.0,
            "sector_winner_share": 1.0,
            "sector_mean_len_mean": 1.0,
        }

    center_n = sample_normal(img, pos[None, :])[0]
    phi, anisotropy, tensor = compute_eigen(img, pos, args.radius, args.stddev, tensor_offsets, tensor_weights)

    sx = args.alpha / max(args.alpha + anisotropy, EPSILON)
    sy = (args.alpha + anisotropy) / max(args.alpha, EPSILON)
    c = math.cos(phi)
    s = math.sin(phi)

    m_xyz = np.zeros((SECTORS, 3), dtype=np.float64)
    m_rgb = np.zeros((SECTORS, 3), dtype=np.float64)
    m_rgb2 = np.zeros((SECTORS, 3), dtype=np.float64)
    m_w = np.zeros(SECTORS, dtype=np.float64)

    unit = disk_offsets / max(float(args.radius), 1.0)
    rotated = np.empty_like(unit)
    rotated[:, 0] = c * unit[:, 0] - s * unit[:, 1]
    rotated[:, 1] = s * unit[:, 0] + c * unit[:, 1]
    sr = np.stack([sx * rotated[:, 0], sy * rotated[:, 1]], axis=-1)
    include = np.ones(len(disk_offsets), dtype=bool)
    if args.mode == "fixed":
        include = np.sum(sr * sr, axis=-1) <= 1.0

    for sign in (1.0, -1.0):
        offsets = disk_offsets[include]
        normals = sample_normal(img, pos[None, :] + sign * offsets)
        rgbs = sample_rgb(img, pos[None, :] + sign * offsets)
        sr_signed = sign * sr[include]
        angles = np.arctan2(sr_signed[:, 1], sr_signed[:, 0])
        angles = np.where(angles < 0.0, angles + TWO_PI, angles)
        sector_f = angles * (SECTORS / TWO_PI)
        sector_a = np.floor(sector_f).astype(np.int32)
        sector_b = (sector_a + 1) % SECTORS
        t = sector_f - sector_a
        wa = 1.0 - t
        wb = t

        for sector in range(SECTORS):
            mask_a = sector_a == sector
            mask_b = sector_b == sector
            if np.any(mask_a):
                w = wa[mask_a, None]
                m_xyz[sector] += np.sum(normals[mask_a] * w, axis=0)
                m_rgb[sector] += np.sum(rgbs[mask_a] * w, axis=0)
                m_rgb2[sector] += np.sum((rgbs[mask_a] * rgbs[mask_a]) * w, axis=0)
                m_w[sector] += float(np.sum(wa[mask_a]))
            if np.any(mask_b):
                w = wb[mask_b, None]
                m_xyz[sector] += np.sum(normals[mask_b] * w, axis=0)
                m_rgb[sector] += np.sum(rgbs[mask_b] * w, axis=0)
                m_rgb2[sector] += np.sum((rgbs[mask_b] * rgbs[mask_b]) * w, axis=0)
                m_w[sector] += float(np.sum(wb[mask_b]))

    result_n = np.zeros(3, dtype=np.float64)
    result_w = 0.0
    best_n = center_n
    best_weight = -1.0
    sector_weights = []
    mean_lengths = []

    for i in range(SECTORS):
        if m_w[i] > EPSILON:
            mean_raw = m_xyz[i] / m_w[i]
            mean_len = float(np.linalg.norm(mean_raw))
            mean_n = mean_raw / mean_len if mean_len > EPSILON else center_n
            normal_variance = 1.0 - np.clip(mean_len, 0.0, 1.0)
            if args.mode == "fixed":
                mean_rgb = m_rgb[i] / m_w[i]
                rgb_variance = np.maximum(m_rgb2[i] / m_w[i] - mean_rgb * mean_rgb, 0.0)
                variance = max(float(normal_variance), float(np.mean(rgb_variance)))
                sector_weight = (1.0 / (1.0 + FIXED_VARIANCE_SCALE * variance)) ** max(args.sharpness, 1.0)
            else:
                variance = normal_variance
                sector_weight = 1.0 / (1.0 + (VARIANCE_SCALE * variance) ** args.sharpness)
            result_n += sector_weight * mean_n
            result_w += sector_weight
            if sector_weight > best_weight:
                best_weight = sector_weight
                best_n = mean_n
            sector_weights.append(float(sector_weight))
            mean_lengths.append(mean_len)

    if args.mode == "fixed":
        filtered = normalize(best_n[None, :])[0] if best_weight > 0.0 else center_n
    else:
        filtered = normalize((result_n / result_w)[None, :])[0] if result_w > EPSILON else center_n
    final = normalize((center_n * (1.0 - np.clip(args.strength, 0.0, 1.0)) + filtered * np.clip(args.strength, 0.0, 1.0))[None, :])[0]
    return {
        "encoded": final * 0.5 + 0.5,
        "normal": final,
        "center_normal": center_n,
        "anisotropy": anisotropy,
        "tensor": tensor,
        "sector_weight_mean": float(np.mean(sector_weights)) if sector_weights else 0.0,
        "sector_weight_min": float(np.min(sector_weights)) if sector_weights else 0.0,
        "sector_weight_max": float(np.max(sector_weights)) if sector_weights else 0.0,
        "sector_winner_share": float(np.max(sector_weights) / max(np.sum(sector_weights), EPSILON)) if sector_weights else 0.0,
        "sector_mean_len_mean": float(np.mean(mean_lengths)) if mean_lengths else 0.0,
    }


def make_offsets(radius, stddev):
    ints = np.arange(-radius, radius + 1, dtype=np.float32)
    xx, yy = np.meshgrid(ints, ints)

    disk_mask = (xx * xx + yy * yy) <= float(radius * radius)
    disk_offsets = np.stack([xx[disk_mask], yy[disk_mask]], axis=-1).astype(np.float32)

    tensor_offsets = 0.5 * np.stack([xx.ravel(), yy.ravel()], axis=-1).astype(np.float32)
    wx = np.exp(-0.5 * (tensor_offsets[:, 0] ** 2) / max(stddev * stddev, EPSILON))
    wy = np.exp(-0.5 * (tensor_offsets[:, 1] ** 2) / max(stddev * stddev, EPSILON))
    tensor_weights = (wx * wy).astype(np.float32)
    return disk_offsets, tensor_offsets, tensor_weights


def sample_positions(img, alpha, radius, samples, active_threshold):
    height, width, _ = img.shape
    margin = radius + 3
    nx = max(2, int(round(math.sqrt(samples * 9))))
    ny = max(2, int(math.ceil((samples * 9) / nx)))
    xs = np.linspace(margin, width - 1 - margin, nx)
    ys = np.linspace(margin, height - 1 - margin, ny)
    grid = np.stack(np.meshgrid(xs, ys), axis=-1).reshape(-1, 2)
    centers = sample_rgb(img, grid)
    rgb_active = np.linalg.norm(centers, axis=-1) > active_threshold
    alpha_active = sample_alpha(alpha, grid) > active_threshold
    active = grid[rgb_active | alpha_active]
    if len(active) >= samples:
        idx = np.linspace(0, len(active) - 1, samples).round().astype(np.int32)
        return active[idx].astype(np.float32), True
    return grid[:samples].astype(np.float32), False


def sample_alpha(alpha, positions):
    h, w = alpha.shape
    p = np.asarray(positions, dtype=np.float32)
    x = np.clip(p[..., 0], 0.0, w - 1.0)
    y = np.clip(p[..., 1], 0.0, h - 1.0)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    tx = x - x0
    ty = y - y0
    c00 = alpha[y0, x0]
    c10 = alpha[y0, x1]
    c01 = alpha[y1, x0]
    c11 = alpha[y1, x1]
    return (c00 * (1.0 - tx) + c10 * tx) * (1.0 - ty) + (c01 * (1.0 - tx) + c11 * tx) * ty


def percentile(values, p):
    return float(np.percentile(values, p)) if len(values) else 0.0


def heat_color(t):
    t = float(np.clip(t, 0.0, 1.0))
    stops = np.array(
        [
            [40, 80, 220],
            [40, 210, 170],
            [245, 205, 55],
            [230, 70, 45],
        ],
        dtype=np.float32,
    )
    scaled = t * (len(stops) - 1)
    i = int(np.floor(scaled))
    j = min(i + 1, len(stops) - 1)
    f = scaled - i
    return tuple(np.round(stops[i] * (1.0 - f) + stops[j] * f).astype(np.uint8))


def write_overlay(path, img, positions, angle_deg, size=768):
    h, w, _ = img.shape
    preview = np.clip(img, 0.0, 1.0)
    preview = (preview ** (1.0 / 2.2) * 255.0).astype(np.uint8)
    im = Image.fromarray(preview, "RGB")
    im.thumbnail((size, size), Image.Resampling.LANCZOS)
    sx = im.width / w
    sy = im.height / h
    draw = ImageDraw.Draw(im)
    for pos, angle in zip(positions, angle_deg):
        x = float(pos[0] * sx)
        y = float(pos[1] * sy)
        r = 4
        color = heat_color(angle / 30.0)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(0, 0, 0), width=2)
        draw.ellipse((x - r + 1, y - r + 1, x + r - 1, y + r - 1), fill=color)
    im.save(path)


def main():
    parser = argparse.ArgumentParser(description="Sparse CPU probe for the pasted anisotropic Kuwahara normal filter.")
    parser.add_argument("--image", default=r"C:\Users\singerie\Documents\Cursor\paint\hehe.EXR")
    parser.add_argument("--radius", type=int, default=32)
    parser.add_argument("--stddev", type=float, default=4.0)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--sharpness", type=float, default=4.0)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--samples", type=int, default=144)
    parser.add_argument("--active-threshold", type=float, default=0.02)
    parser.add_argument("--overlay", default="")
    parser.add_argument("--mode", choices=["original", "fixed"], default="original")
    args = parser.parse_args()

    path = Path(args.image)
    if not path.exists():
        raise SystemExit(f"Image not found: {path}")

    img, alpha, pix_fmt = load_exr_rgba(path)
    height, width, _ = img.shape
    disk_offsets, tensor_offsets, tensor_weights = make_offsets(args.radius, args.stddev)
    positions, active_only = sample_positions(img, alpha, args.radius, args.samples, args.active_threshold)

    outputs = []
    inputs = []
    anisotropy = []
    sector_weight_mean = []
    sector_weight_min = []
    sector_weight_max = []
    sector_winner_share = []
    sector_mean_len_mean = []

    for i, pos in enumerate(positions):
        if i and i % 24 == 0:
            print(f"processed {i}/{len(positions)} samples...", file=sys.stderr)
        out = filter_pixel(img, pos, args, disk_offsets, tensor_offsets, tensor_weights)
        inp = sample_rgb(img, pos[None, :])[0]
        outputs.append(out["encoded"])
        inputs.append(inp)
        anisotropy.append(out["anisotropy"])
        sector_weight_mean.append(out["sector_weight_mean"])
        sector_weight_min.append(out["sector_weight_min"])
        sector_weight_max.append(out["sector_weight_max"])
        sector_winner_share.append(out["sector_winner_share"])
        sector_mean_len_mean.append(out["sector_mean_len_mean"])

    inputs = np.asarray(inputs, dtype=np.float32)
    outputs = np.asarray(outputs, dtype=np.float32)
    in_n = normalize(inputs * 2.0 - 1.0)
    out_n = normalize(outputs * 2.0 - 1.0)

    abs_delta = np.abs(outputs - inputs)
    rgb_len_delta = np.linalg.norm(outputs - inputs, axis=-1)
    dots = np.clip(np.sum(in_n * out_n, axis=-1), -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(dots))

    print("AKF sparse probe")
    print(f"image: {path}")
    print(f"size: {width}x{height}, source pix_fmt: {pix_fmt}")
    print(
        "params: "
        f"radius={args.radius}, stddev={args.stddev}, alpha={args.alpha}, "
        f"sharpness={args.sharpness}, strength={args.strength}, samples={len(positions)}"
    )
    print(f"input rgb range: min={float(np.min(img)):.6f}, max={float(np.max(img)):.6f}")
    print(f"input alpha range: min={float(np.min(alpha)):.6f}, max={float(np.max(alpha)):.6f}")
    print(f"sample selection: {'active rgb/alpha texels' if active_only else 'full grid fallback'}")
    print(f"kernel taps: disk={len(disk_offsets)}, tensor={len(tensor_offsets)} per sampled pixel")
    print("")
    print("encoded RGB delta, 0..1 units")
    print(f"  mean_abs_channel: {float(np.mean(abs_delta)):.8f}")
    print(f"  mean_rgb_length:  {float(np.mean(rgb_len_delta)):.8f}")
    print(f"  p50_rgb_length:   {percentile(rgb_len_delta, 50):.8f}")
    print(f"  p95_rgb_length:   {percentile(rgb_len_delta, 95):.8f}")
    print(f"  max_rgb_length:   {float(np.max(rgb_len_delta)):.8f}")
    print("")
    print("encoded RGB delta, 8-bit equivalent")
    print(f"  mean_abs_channel: {float(np.mean(abs_delta) * 255.0):.4f}")
    print(f"  p95_rgb_length:   {percentile(rgb_len_delta, 95) * 255.0:.4f}")
    print(f"  max_rgb_length:   {float(np.max(rgb_len_delta) * 255.0):.4f}")
    print("")
    print("normal direction delta")
    print(f"  mean_angle_deg: {float(np.mean(angle_deg)):.6f}")
    print(f"  p50_angle_deg:  {percentile(angle_deg, 50):.6f}")
    print(f"  p95_angle_deg:  {percentile(angle_deg, 95):.6f}")
    print(f"  max_angle_deg:  {float(np.max(angle_deg)):.6f}")
    print("")
    print("internal shader diagnostics")
    print(f"  anisotropy mean/p95/max: {float(np.mean(anisotropy)):.6f} / {percentile(anisotropy, 95):.6f} / {float(np.max(anisotropy)):.6f}")
    print(
        "  sector weight mean/min/max averages: "
        f"{float(np.mean(sector_weight_mean)):.6f} / {float(np.mean(sector_weight_min)):.6f} / {float(np.mean(sector_weight_max)):.6f}"
    )
    print(
        "  winning sector share mean/p50/p95: "
        f"{float(np.mean(sector_winner_share)):.6f} / {percentile(sector_winner_share, 50):.6f} / {percentile(sector_winner_share, 95):.6f}"
    )
    print(f"  sector mean length avg: {float(np.mean(sector_mean_len_mean)):.6f}")

    if args.overlay:
        write_overlay(args.overlay, img, positions, angle_deg)
        print(f"overlay: {args.overlay}")


if __name__ == "__main__":
    main()
