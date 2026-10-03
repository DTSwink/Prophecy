import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


EPS = 1e-5
SECTORS = 8
TWO_PI = 6.28318530718


def ffprobe_size(path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def load_exr(path, size=0):
    src_w, src_h = ffprobe_size(path)
    w = h = int(size) if size else src_w
    vf = ["-vf", f"scale={w}:{h}:flags=lanczos"] if size else []
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            *vf,
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
    rgba = np.frombuffer(raw, dtype=np.uint16).reshape(h, w, 4).astype(np.float32) / 65535.0
    return rgba[..., :3], rgba[..., 3]


def normalize(v):
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(l > EPS, v / np.maximum(l, EPS), np.array([0.0, 0.0, 1.0], dtype=np.float32))


def roll_clamped(a, ox, oy):
    h, w = a.shape[:2]
    ys = np.clip(np.arange(h) + oy, 0, h - 1)
    xs = np.clip(np.arange(w) + ox, 0, w - 1)
    return a[ys[:, None], xs[None, :]]


def gaussian_blur(arr, sigma):
    radius = max(1, int(math.ceil(sigma * 3.0)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x * x) / max(sigma * sigma, EPS))
    k /= np.sum(k)

    tmp = np.zeros_like(arr)
    out = np.zeros_like(arr)
    for i, weight in zip(range(-radius, radius + 1), k):
        tmp += weight * roll_clamped(arr, i, 0)
    for i, weight in zip(range(-radius, radius + 1), k):
        out += weight * roll_clamped(tmp, 0, i)
    return out


def structure_orientation(rgb, stddev):
    n = normalize(rgb * 2.0 - 1.0)
    fx = (
        -roll_clamped(n, -1, -1)
        - 2.0 * roll_clamped(n, -1, 0)
        - roll_clamped(n, -1, 1)
        + roll_clamped(n, 1, -1)
        + 2.0 * roll_clamped(n, 1, 0)
        + roll_clamped(n, 1, 1)
    ) * 0.25
    fy = (
        -roll_clamped(n, -1, -1)
        - 2.0 * roll_clamped(n, 0, -1)
        - roll_clamped(n, 1, -1)
        + roll_clamped(n, -1, 1)
        + 2.0 * roll_clamped(n, 0, 1)
        + roll_clamped(n, 1, 1)
    ) * 0.25
    tensor = np.stack([np.sum(fx * fx, axis=-1), np.sum(fx * fy, axis=-1), np.sum(fy * fy, axis=-1)], axis=-1)
    g = gaussian_blur(tensor, stddev)
    disc = np.sqrt(np.maximum((g[..., 0] - g[..., 2]) ** 2 + 4.0 * g[..., 1] ** 2, EPS))
    l1 = 0.5 * (g[..., 0] + g[..., 2] + disc)
    l2 = 0.5 * (g[..., 0] + g[..., 2] - disc)
    tx = l1 - g[..., 0]
    ty = -g[..., 1]
    tl = np.sqrt(tx * tx + ty * ty)
    tx = np.where(tl > EPS, tx / np.maximum(tl, EPS), 0.0)
    ty = np.where(tl > EPS, ty / np.maximum(tl, EPS), 1.0)
    phi = np.arctan2(ty, tx)
    anisotropy = np.clip((l1 - l2) / np.maximum(l1 + l2, EPS), 0.0, 1.0)
    return phi, anisotropy


def render_filter(rgb, alpha, radius, stddev, anis_alpha, sharpness, strength, fixed, winner_blend=1.0):
    h, w, _ = rgb.shape
    center_n = normalize(rgb * 2.0 - 1.0)
    phi, aniso = structure_orientation(rgb, stddev)
    sx = anis_alpha / np.maximum(anis_alpha + aniso, EPS)
    sy = (anis_alpha + aniso) / max(anis_alpha, EPS)
    c = np.cos(phi)
    s = np.sin(phi)

    normal_sum = np.zeros((SECTORS, h, w, 3), dtype=np.float32)
    rgb_sum = np.zeros((SECTORS, h, w, 3), dtype=np.float32)
    rgb_sq_sum = np.zeros((SECTORS, h, w, 3), dtype=np.float32)
    weight_sum = np.zeros((SECTORS, h, w), dtype=np.float32)

    offsets = [(x, y) for y in range(-radius, radius + 1) for x in range(-radius, radius + 1) if x * x + y * y <= radius * radius]
    for x, y in offsets:
        ux = float(x) / max(float(radius), 1.0)
        uy = float(y) / max(float(radius), 1.0)
        rx = c * ux - s * uy
        ry = s * ux + c * uy
        sr_x = sx * rx
        sr_y = sy * ry
        include = (sr_x * sr_x + sr_y * sr_y) <= 1.0 if fixed else np.ones((h, w), dtype=bool)

        raw = roll_clamped(rgb, x, y)
        n = normalize(raw * 2.0 - 1.0)
        ang = np.arctan2(sr_y, sr_x)
        ang = np.where(ang < 0.0, ang + TWO_PI, ang)
        sf = ang * (SECTORS / TWO_PI)
        sa = np.floor(sf).astype(np.int32)
        sb = (sa + 1) % SECTORS
        t = sf - sa

        for sector in range(SECTORS):
            wa = np.where((sa == sector) & include, 1.0 - t, 0.0).astype(np.float32)
            wb = np.where((sb == sector) & include, t, 0.0).astype(np.float32)
            ww = wa + wb
            normal_sum[sector] += n * ww[..., None]
            rgb_sum[sector] += raw * ww[..., None]
            rgb_sq_sum[sector] += raw * raw * ww[..., None]
            weight_sum[sector] += ww

    valid = weight_sum > EPS
    mean_n_raw = normal_sum / np.maximum(weight_sum[..., None], EPS)
    mean_len = np.linalg.norm(mean_n_raw, axis=-1)
    mean_n = np.where(mean_len[..., None] > EPS, mean_n_raw / np.maximum(mean_len[..., None], EPS), center_n[None, ...])
    normal_var = 1.0 - np.clip(mean_len, 0.0, 1.0)

    if fixed:
        mean_rgb = rgb_sum / np.maximum(weight_sum[..., None], EPS)
        rgb_var = np.maximum(rgb_sq_sum / np.maximum(weight_sum[..., None], EPS) - mean_rgb * mean_rgb, 0.0)
        var = np.maximum(normal_var, np.mean(rgb_var, axis=-1))
        sector_weight = (1.0 / (1.0 + 384.0 * var)) ** max(sharpness, 1.0)
        sector_weight = np.where(valid, sector_weight, -1.0)
        best = np.argmax(sector_weight, axis=0)
        yy, xx = np.indices((h, w))
        best_n = mean_n[best, yy, xx]
        weighted = normalize(np.sum(mean_n * np.maximum(sector_weight, 0.0)[..., None], axis=0) / np.maximum(np.sum(np.maximum(sector_weight, 0.0), axis=0)[..., None], EPS))
        filtered = normalize(weighted * (1.0 - winner_blend) + best_n * winner_blend)
    else:
        var = normal_var
        sector_weight = 1.0 / (1.0 + (64.0 * var) ** sharpness)
        sector_weight = np.where(valid, sector_weight, 0.0)
        filtered = normalize(np.sum(mean_n * sector_weight[..., None], axis=0) / np.maximum(np.sum(sector_weight, axis=0)[..., None], EPS))

    final_n = normalize(center_n * (1.0 - strength) + filtered * strength)
    out = final_n * 0.5 + 0.5
    preserve = (np.max(rgb, axis=-1) < 0.005) | (np.min(rgb, axis=-1) > 0.995)
    if fixed:
        out = np.where(preserve[..., None], rgb, out)
    out = np.where((alpha > 0.01)[..., None] | (np.linalg.norm(rgb, axis=-1) > 0.02)[..., None], out, rgb)
    return np.clip(out, 0.0, 1.0)


def label(im, text):
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    draw.rectangle((0, 0, im.width, box[3] + 18), fill=(0, 0, 0))
    draw.text((10, 8), text, fill=(255, 255, 255), font=font)


def to_preview(rgb):
    arr = np.clip(rgb ** (1.0 / 2.2) * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", default=r"C:\Users\singerie\Documents\Cursor\paint\hehe.EXR")
    p.add_argument("--size", type=int, default=384)
    p.add_argument("--radius", type=int, default=64)
    p.add_argument("--stddev", type=float, default=4.0)
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--sharpness", type=float, default=4.0)
    p.add_argument("--strength", type=float, default=1.0)
    p.add_argument("--winner-blend", type=float, default=0.65)
    p.add_argument("--out", default=r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\akf_visual_comparison.png")
    args = p.parse_args()

    rgb, alpha = load_exr(Path(args.image), args.size)
    scale = args.size / 2048.0
    radius = max(2, int(round(args.radius * scale)))
    stddev = max(0.5, args.stddev * scale)

    original = to_preview(rgb)
    old = to_preview(render_filter(rgb, alpha, radius, stddev, args.alpha, args.sharpness, args.strength, fixed=False))
    fixed = to_preview(render_filter(rgb, alpha, radius, stddev, args.alpha, args.sharpness, args.strength, fixed=True, winner_blend=args.winner_blend))

    label(original, "Original EXR")
    label(old, f"Old shader approx, R{args.radius}")
    label(fixed, f"Fixed cleaner sectors, R{args.radius}")

    gap = 8
    canvas = Image.new("RGB", (original.width * 3 + gap * 2, original.height), (20, 20, 20))
    canvas.paste(original, (0, 0))
    canvas.paste(old, (original.width + gap, 0))
    canvas.paste(fixed, ((original.width + gap) * 2, 0))
    canvas.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
