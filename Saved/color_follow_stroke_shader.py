import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def load_image(path, max_size=0):
    path = Path(path)
    if path.suffix.lower() == ".exr":
        w, h = probe_size(path)
        if max_size and max(w, h) > max_size:
            scale = max_size / max(w, h)
            w2 = max(1, int(round(w * scale)))
            h2 = max(1, int(round(h * scale)))
            vf = ["-vf", f"scale={w2}:{h2}:flags=lanczos"]
            w, h = w2, h2
        else:
            vf = []
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

    im = Image.open(path).convert("RGBA")
    if max_size and max(im.size) > max_size:
        im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    rgba = np.asarray(im).astype(np.float32) / 255.0
    return rgba[..., :3], rgba[..., 3]


def probe_size(path):
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


def save_png(path, rgb, alpha=None):
    rgb8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    if alpha is None:
        Image.fromarray(rgb8, "RGB").save(path)
    else:
        a8 = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
        Image.fromarray(np.dstack([rgb8, a8]), "RGBA").save(path)


def smooth(arr, radius):
    if radius <= 0:
        return arr
    im = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "L")
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255.0


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.max(rgb, axis=-1)
    mn = np.min(rgb, axis=-1)
    d = mx - mn
    h = np.zeros_like(mx)
    mask = d > 1e-6
    mr = mask & (mx == r)
    mg = mask & (mx == g)
    mb = mask & (mx == b)
    h[mr] = ((g[mr] - b[mr]) / d[mr]) % 6.0
    h[mg] = (b[mg] - r[mg]) / d[mg] + 2.0
    h[mb] = (r[mb] - g[mb]) / d[mb] + 4.0
    h /= 6.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return np.stack([h, s, mx], axis=-1)


def hsv_to_rgb(hsv):
    h = (hsv[..., 0] % 1.0) * 6.0
    s = np.clip(hsv[..., 1], 0.0, 1.0)
    v = np.clip(hsv[..., 2], 0.0, 1.0)
    c = v * s
    x = c * (1.0 - np.abs((h % 2.0) - 1.0))
    m = v - c
    z = np.zeros_like(h)
    out = np.zeros(hsv.shape, dtype=np.float32)
    zones = [
        (h < 1.0, c, x, z),
        ((h >= 1.0) & (h < 2.0), x, c, z),
        ((h >= 2.0) & (h < 3.0), z, c, x),
        ((h >= 3.0) & (h < 4.0), z, x, c),
        ((h >= 4.0) & (h < 5.0), x, z, c),
        (h >= 5.0, c, z, x),
    ]
    for mask, rr, gg, bb in zones:
        out[..., 0] = np.where(mask, rr, out[..., 0])
        out[..., 1] = np.where(mask, gg, out[..., 1])
        out[..., 2] = np.where(mask, bb, out[..., 2])
    return out + m[..., None]


def local_mean(rgb, x, y, r):
    h, w, _ = rgb.shape
    x = float(np.clip(x, 0, w - 1))
    y = float(np.clip(y, 0, h - 1))
    x0 = max(0, int(x - r))
    x1 = min(w, int(x + r + 1))
    y0 = max(0, int(y - r))
    y1 = min(h, int(y + r + 1))
    return np.mean(rgb[y0:y1, x0:x1], axis=(0, 1))


def structure_maps(rgb, alpha):
    hsv = rgb_to_hsv(rgb)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    hue_vec = np.stack([np.cos(hsv[..., 0] * math.tau), np.sin(hsv[..., 0] * math.tau)], axis=-1) * hsv[..., 1:2]
    feature = np.dstack([luma, hsv[..., 1], hue_vec])

    gx = np.zeros(feature.shape[:2], dtype=np.float32)
    gy = np.zeros(feature.shape[:2], dtype=np.float32)
    for c in range(feature.shape[2]):
        ch = feature[..., c]
        dx = np.zeros_like(ch)
        dy = np.zeros_like(ch)
        dx[:, 1:-1] = ch[:, 2:] - ch[:, :-2]
        dy[1:-1, :] = ch[2:, :] - ch[:-2, :]
        gx += dx * dx
        gy += dy * dy

    grad = np.sqrt(gx + gy)
    edge = smooth(np.clip(grad * 3.5, 0.0, 1.0), 1.2)
    stability = 1.0 - np.clip(edge, 0.0, 1.0)

    dx_l = np.zeros_like(luma)
    dy_l = np.zeros_like(luma)
    dx_l[:, 1:-1] = luma[:, 2:] - luma[:, :-2]
    dy_l[1:-1, :] = luma[2:, :] - luma[:-2, :]
    angle = np.arctan2(dy_l, dx_l) + math.pi * 0.5

    if np.mean(alpha > 0.03) > 0.80:
        fg = (hsv[..., 1] > 0.14) & (hsv[..., 2] > 0.12)
    else:
        fg = (alpha > 0.03) | ((hsv[..., 1] > 0.08) & (hsv[..., 2] > 0.06))
    return edge, stability, angle, fg


def polygon(cx, cy, rx, ry, angle, sides, jitter, rng):
    pts = []
    phase = rng.uniform(0, math.tau)
    ca = math.cos(angle)
    sa = math.sin(angle)
    for i in range(sides):
        t = phase + math.tau * i / sides
        jr = 1.0 + rng.uniform(-jitter, jitter)
        px = math.cos(t) * rx * jr
        py = math.sin(t) * ry * jr
        pts.append((cx + ca * px - sa * py, cy + sa * px + ca * py))
    return pts


def render_strokes(rgb, alpha, seed=7, max_stroke=72, min_stroke=8, density=0.82, handmade=0.08):
    h, w, _ = rgb.shape
    rng = np.random.default_rng(seed)
    edge, stability, angle_map, fg = structure_maps(rgb, alpha)

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    canvas = Image.fromarray(out, "RGBA")
    mask_img = Image.fromarray((fg.astype(np.uint8) * 255), "L")

    passes = [
        (max_stroke, "stable", 0.78, 0.52),
        (int(max_stroke * 0.58), "stable", 0.48, 0.62),
        (int(max_stroke * 0.34), "any", 0.00, 0.68),
        (max(min_stroke, int(max_stroke * 0.20)), "edge", 0.18, 0.78),
        (max(min_stroke, int(max_stroke * 0.12)), "edge", 0.34, 0.62),
    ]

    for base, mode, threshold, opacity in passes:
        base = max(min_stroke, int(base))
        step = max(3, int(base * density))
        xs = np.arange(0, w, step)
        ys = np.arange(0, h, step)
        centers = [(x + rng.uniform(0, step), y + rng.uniform(0, step)) for y in ys for x in xs]
        rng.shuffle(centers)

        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        for cx, cy in centers:
            ix = int(np.clip(cx, 0, w - 1))
            iy = int(np.clip(cy, 0, h - 1))
            if not fg[iy, ix]:
                continue

            stable = stability[iy, ix]
            noisy_stable = stable + rng.uniform(-0.18, 0.18)
            local_edge = edge[iy, ix]
            noisy_edge = local_edge + rng.uniform(-0.12, 0.12)
            if mode == "stable" and noisy_stable < threshold:
                continue
            if mode == "edge" and noisy_edge < threshold:
                continue

            scale = min_stroke + (base - min_stroke) * np.clip(stable, 0.0, 1.0)
            if mode == "edge":
                scale = min_stroke + (base - min_stroke) * np.clip(1.0 - stable, 0.25, 1.0)
            scale *= rng.uniform(0.72, 1.32)

            orient = angle_map[iy, ix] + rng.normal(0.0, 0.35 + 0.55 * handmade)
            aspect = rng.uniform(1.05, 2.35) * (1.0 + 0.7 * stable)
            rx = scale * aspect
            ry = scale * rng.uniform(0.38, 0.78)
            sides = int(rng.integers(5, 9))

            center_color = rgb[iy, ix]
            mean_color = local_mean(rgb, cx, cy, max(2, int(scale * 0.28)))
            color = center_color * 0.68 + mean_color * 0.32
            hsv = rgb_to_hsv(color[None, None, :])[0, 0]
            hsv[0] += rng.normal(0.0, 0.006 + 0.012 * handmade)
            hsv[1] *= rng.uniform(0.95, 1.09)
            hsv[2] *= rng.uniform(0.96, 1.06)
            color = hsv_to_rgb(hsv[None, None, :])[0, 0]
            color = np.clip(color, 0.0, 1.0)

            a = int(255 * opacity * (0.78 + 0.22 * stable))
            pts = polygon(cx, cy, rx, ry, orient, sides, 0.20 + 0.20 * handmade, rng)
            fill = tuple(np.clip(color * 255.0, 0, 255).astype(np.uint8).tolist() + [a])
            draw.polygon(pts, fill=fill)

            if rng.random() < 0.28 + 0.22 * local_edge:
                hi = np.clip(color * rng.uniform(1.04, 1.18), 0.0, 1.0)
                a2 = int(a * rng.uniform(0.18, 0.34))
                pts2 = polygon(cx + rng.normal(0, ry * 0.25), cy + rng.normal(0, ry * 0.25), rx * 0.55, ry * 0.28, orient, sides, 0.25, rng)
                draw.polygon(pts2, fill=tuple(np.clip(hi * 255.0, 0, 255).astype(np.uint8).tolist() + [a2]))

        layer.putalpha(ImageChops_multiply(layer.getchannel("A"), mask_img))
        canvas = Image.alpha_composite(canvas, layer)

    final = np.asarray(canvas).astype(np.float32) / 255.0
    final_rgb = final[..., :3]
    final_rgb = np.where(fg[..., None], final_rgb, rgb)
    final_alpha = np.where(fg, np.maximum(final[..., 3], alpha), alpha)
    return final_rgb, final_alpha, {"edge": edge, "stability": stability, "foreground": fg.astype(np.float32)}


def block_stats(rgb, edge, fg, x0, y0, x1, y1):
    region_mask = fg[y0:y1, x0:x1]
    if not np.any(region_mask):
        return 0.0, 0.0, np.zeros(3, dtype=np.float32)
    region = rgb[y0:y1, x0:x1][region_mask]
    mean = np.mean(region, axis=0)
    var = float(np.mean(np.sum((region - mean) ** 2, axis=-1)))
    edge_mean = float(np.mean(edge[y0:y1, x0:x1][region_mask]))
    return var, edge_mean, mean


def render_adaptive_facets(rgb, alpha, seed=7, max_stroke=72, min_stroke=8, handmade=0.08, detail_bias=1.0):
    h, w, _ = rgb.shape
    rng = np.random.default_rng(seed)
    edge, stability, angle_map, fg = structure_maps(rgb, alpha)

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    canvas = Image.fromarray(out, "RGBA")
    facet_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(facet_layer, "RGBA")

    root = max(min_stroke * 2, int(max_stroke))
    threshold = 0.007 / max(detail_bias, 1e-3)
    edge_threshold = 0.13 / max(detail_bias, 1e-3)
    blocks = [(x, y, min(x + root, w), min(y + root, h)) for y in range(0, h, root) for x in range(0, w, root)]
    leaves = []

    while blocks:
        x0, y0, x1, y1 = blocks.pop()
        bw = x1 - x0
        bh = y1 - y0
        if bw <= 0 or bh <= 0:
            continue
        var, edge_mean, mean = block_stats(rgb, edge, fg, x0, y0, x1, y1)
        if not np.any(fg[y0:y1, x0:x1]):
            continue
        split_score = var * 2.4 + edge_mean * 0.22
        should_split = (bw > min_stroke * 1.7 or bh > min_stroke * 1.7) and (
            split_score > threshold or edge_mean > edge_threshold or rng.random() < 0.08 * handmade
        )
        if should_split:
            mx = (x0 + x1) // 2
            my = (y0 + y1) // 2
            blocks.extend([(x0, y0, mx, my), (mx, y0, x1, my), (x0, my, mx, y1), (mx, my, x1, y1)])
        else:
            leaves.append((x0, y0, x1, y1, mean, edge_mean))

    rng.shuffle(leaves)
    for x0, y0, x1, y1, mean, edge_mean in leaves:
        bw = x1 - x0
        bh = y1 - y0
        if bw <= 1 or bh <= 1:
            continue

        jitter = min(bw, bh) * (0.18 + 0.18 * handmade)
        p00 = (x0 + rng.uniform(-jitter, jitter), y0 + rng.uniform(-jitter, jitter))
        p10 = (x1 + rng.uniform(-jitter, jitter), y0 + rng.uniform(-jitter, jitter))
        p11 = (x1 + rng.uniform(-jitter, jitter), y1 + rng.uniform(-jitter, jitter))
        p01 = (x0 + rng.uniform(-jitter, jitter), y1 + rng.uniform(-jitter, jitter))
        cx = (x0 + x1) * 0.5 + rng.uniform(-jitter, jitter)
        cy = (y0 + y1) * 0.5 + rng.uniform(-jitter, jitter)
        pc = (cx, cy)

        tris = [(p00, p10, pc), (p10, p11, pc), (p11, p01, pc), (p01, p00, pc)]
        if max(bw, bh) < min_stroke * 1.5 and rng.random() < 0.45:
            tris = [(p00, p10, p11), (p00, p11, p01)] if rng.random() < 0.5 else [(p00, p10, p01), (p10, p11, p01)]

        for tri in tris:
            tx = int(np.clip(sum(p[0] for p in tri) / 3.0, 0, w - 1))
            ty = int(np.clip(sum(p[1] for p in tri) / 3.0, 0, h - 1))
            if not fg[ty, tx]:
                continue
            sx = int(np.clip(tx + rng.normal(0.0, max(1.0, bw * 0.22)), x0, max(x0, x1 - 1)))
            sy = int(np.clip(ty + rng.normal(0.0, max(1.0, bh * 0.22)), y0, max(y0, y1 - 1)))
            if not fg[sy, sx]:
                sx, sy = tx, ty
            center_color = rgb[ty, tx]
            pulled_color = rgb[sy, sx]
            color = center_color * 0.44 + pulled_color * 0.38 + mean * 0.18
            hsv = rgb_to_hsv(color[None, None, :])[0, 0]
            hsv[0] += rng.normal(0.0, 0.010 + 0.055 * handmade)
            hsv[1] *= rng.uniform(0.88, 1.24)
            hsv[2] *= rng.uniform(0.84, 1.20)
            color = np.clip(hsv_to_rgb(hsv[None, None, :])[0, 0], 0.0, 1.0)
            alpha_fill = int(255 * (0.92 + 0.08 * np.clip(edge_mean, 0.0, 1.0)))
            draw.polygon(tri, fill=tuple(np.clip(color * 255.0, 0, 255).astype(np.uint8).tolist() + [alpha_fill]))

            if edge_mean > 0.16 and rng.random() < 0.35:
                cx = sum(p[0] for p in tri) / 3.0
                cy = sum(p[1] for p in tri) / 3.0
                mini = []
                for px, py in tri:
                    mini.append((cx + (px - cx) * rng.uniform(0.35, 0.72), cy + (py - cy) * rng.uniform(0.35, 0.72)))
                accent = np.clip(color * rng.uniform(0.75, 1.28), 0.0, 1.0)
                draw.polygon(mini, fill=tuple(np.clip(accent * 255.0, 0, 255).astype(np.uint8).tolist() + [int(alpha_fill * 0.45)]))

    mask_img = Image.fromarray((fg.astype(np.uint8) * 255), "L")
    facet_layer.putalpha(ImageChops_multiply(facet_layer.getchannel("A"), mask_img))
    canvas = Image.alpha_composite(canvas, facet_layer)
    final = np.asarray(canvas).astype(np.float32) / 255.0
    return final[..., :3], np.maximum(final[..., 3], alpha), {"edge": edge, "stability": stability, "foreground": fg.astype(np.float32)}


def brush_alpha(length, width, handmade, rng):
    length = max(4, int(length))
    width = max(3, int(width))
    x = np.linspace(-1.0, 1.0, length, dtype=np.float32)[None, :]
    y = np.linspace(-1.0, 1.0, width, dtype=np.float32)[:, None]
    body = np.clip(1.0 - np.abs(y) ** 2.6, 0.0, 1.0)
    taper = np.clip(1.0 - np.abs(x) ** 5.0, 0.0, 1.0)
    envelope = body * taper

    bristles = np.ones((width, length), dtype=np.float32)
    stripe_count = max(4, int(width * (0.30 + handmade * 0.35)))
    for _ in range(stripe_count):
        cy = rng.uniform(0, width - 1)
        sigma = rng.uniform(0.35, max(0.7, width * 0.055))
        strength = rng.uniform(0.10, 0.38) * (0.5 + handmade)
        bristles *= 1.0 - strength * np.exp(-0.5 * ((np.arange(width)[:, None] - cy) / sigma) ** 2)

    noise_w = max(2, length // 24)
    noise_h = max(2, width // 3)
    small = rng.uniform(0.55, 1.0, (noise_h, noise_w)).astype(np.float32)
    noise = np.asarray(
        Image.fromarray(np.clip(small * 255, 0, 255).astype(np.uint8), "L").resize((length, width), Image.Resampling.BICUBIC)
    ).astype(np.float32) / 255.0

    dry = np.clip((noise - (0.25 + 0.18 * handmade)) / max(0.25, 0.55 - 0.10 * handmade), 0.0, 1.0)
    alpha = envelope * bristles * (0.58 + 0.42 * dry)

    if handmade > 0.2:
        scratch_count = int(handmade * 9)
        for _ in range(scratch_count):
            yy = int(rng.integers(0, width))
            x0 = int(rng.integers(0, max(1, length - 1)))
            x1 = int(min(length, x0 + rng.integers(max(2, length // 12), max(3, length // 3))))
            alpha[max(0, yy - 1):min(width, yy + 2), x0:x1] *= rng.uniform(0.08, 0.45)

    alpha = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(max(0.15, width * 0.018)))


def stamp_brush(canvas, center, length, width, angle, color, opacity, handmade, rng):
    mask = brush_alpha(length, width, handmade, rng)
    rgba = Image.new("RGBA", mask.size, tuple(np.clip(color * 255.0, 0, 255).astype(np.uint8).tolist() + [0]))
    rgba.putalpha(mask.point(lambda a: int(a * opacity)))
    rotated = rgba.rotate(angle * 180.0 / math.pi, resample=Image.Resampling.BICUBIC, expand=True)
    x = int(center[0] - rotated.width * 0.5)
    y = int(center[1] - rotated.height * 0.5)
    canvas.alpha_composite(rotated, (x, y))


def render_coherent_brushes(rgb, alpha, seed=7, max_stroke=72, min_stroke=8, density=0.82, handmade=0.35, detail_bias=1.0):
    h, w, _ = rgb.shape
    rng = np.random.default_rng(seed)
    edge, stability, angle_map, fg = structure_maps(rgb, alpha)

    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    base[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    canvas = Image.fromarray(base, "RGBA")

    # Big stable strokes first, then progressively smaller/detail strokes.
    passes = [
        ("stable", max_stroke, 0.66, 0.78, 0.52),
        ("stable", max_stroke * 0.66, 0.42, 0.74, 0.48),
        ("any", max_stroke * 0.42, 0.00, 0.70, 0.42),
        ("edge", max_stroke * 0.25, 0.18 / max(detail_bias, 1e-3), 0.78, 0.36),
        ("edge", max_stroke * 0.14, 0.32 / max(detail_bias, 1e-3), 0.66, 0.30),
    ]

    for mode, base_len, threshold, opacity, spacing_mul in passes:
        base_len = max(min_stroke, float(base_len))
        spacing = max(3, int(base_len * spacing_mul * density))
        xs = np.arange(0, w, spacing)
        ys = np.arange(0, h, spacing)
        centers = []
        for y in ys:
            for x in xs:
                centers.append((x + rng.uniform(0, spacing), y + rng.uniform(0, spacing)))
        rng.shuffle(centers)

        for cx, cy in centers:
            ix = int(np.clip(cx, 0, w - 1))
            iy = int(np.clip(cy, 0, h - 1))
            if not fg[iy, ix]:
                continue
            stable = float(stability[iy, ix])
            local_edge = float(edge[iy, ix])
            if mode == "stable" and stable + rng.uniform(-0.16, 0.16) < threshold:
                continue
            if mode == "edge" and local_edge + rng.uniform(-0.10, 0.10) < threshold:
                continue

            if mode == "edge":
                length = base_len * rng.uniform(0.72, 1.35) * (0.75 + 0.75 * local_edge)
                width = length * rng.uniform(0.16, 0.34)
            else:
                length = base_len * rng.uniform(0.85, 1.75) * (0.70 + 0.85 * stable)
                width = length * rng.uniform(0.13, 0.28)

            length = max(min_stroke, length)
            width = max(3.0, width)
            orient = float(angle_map[iy, ix]) + rng.normal(0.0, 0.18 + 0.34 * handmade)

            pull = max(2, int(length * 0.22))
            mean_color = local_mean(rgb, cx, cy, pull)
            # Pull pigment along the stroke direction so colors stay coherent but not flat.
            px = int(np.clip(ix + math.cos(orient) * rng.normal(0, length * 0.20), 0, w - 1))
            py = int(np.clip(iy + math.sin(orient) * rng.normal(0, length * 0.20), 0, h - 1))
            if not fg[py, px]:
                px, py = ix, iy
            color = rgb[iy, ix] * 0.50 + rgb[py, px] * 0.30 + mean_color * 0.20

            hsv = rgb_to_hsv(color[None, None, :])[0, 0]
            hsv[0] += rng.normal(0.0, 0.006 + 0.030 * handmade)
            hsv[1] *= rng.uniform(0.90, 1.18)
            hsv[2] *= rng.uniform(0.88, 1.16)
            color = np.clip(hsv_to_rgb(hsv[None, None, :])[0, 0], 0.0, 1.0)

            stamp_brush(canvas, (cx, cy), length, width, orient, color, opacity, handmade, rng)

    final = np.asarray(canvas).astype(np.float32) / 255.0
    final_rgb = np.where(fg[..., None], final[..., :3], rgb)
    final_alpha = np.where(fg, np.maximum(final[..., 3], alpha), alpha)
    return final_rgb, final_alpha, {"edge": edge, "stability": stability, "foreground": fg.astype(np.float32)}


def ImageChops_multiply(a, b):
    aa = np.asarray(a).astype(np.float32) / 255.0
    bb = np.asarray(b).astype(np.float32) / 255.0
    return Image.fromarray(np.clip(aa * bb * 255.0, 0, 255).astype(np.uint8), "L")


def metrics(src, out, fg):
    diff = np.linalg.norm((out - src) * 255.0, axis=-1)
    hsv_src = rgb_to_hsv(src)
    hsv_out = rgb_to_hsv(out)
    dh = np.abs(hsv_src[..., 0] - hsv_out[..., 0])
    dh = np.minimum(dh, 1.0 - dh) * 360.0
    edge_src = structure_maps(src, fg.astype(np.float32))[0]
    edge_out = structure_maps(out, fg.astype(np.float32))[0]
    if np.any(fg):
        return {
            "mean_rgb_delta_0_255": float(np.mean(diff[fg])),
            "mean_hue_error_degrees": float(np.mean(dh[fg])),
            "mean_saturation_delta": float(np.mean(np.abs(hsv_src[..., 1][fg] - hsv_out[..., 1][fg]))),
            "edge_contrast_ratio": float(np.mean(edge_out[fg]) / max(float(np.mean(edge_src[fg])), 1e-6)),
            "foreground_pct": float(np.mean(fg) * 100.0),
        }
    return {}


def label_panel(im, text):
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", max(14, im.width // 34))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.rectangle((0, 0, im.width, bbox[3] + 14), fill=(10, 12, 16))
    draw.text((8, 6), text, fill=(255, 255, 255), font=font)


def make_contact(src, out, maps, path):
    src_im = Image.fromarray(np.clip(src ** (1 / 2.2) * 255.0, 0, 255).astype(np.uint8), "RGB")
    out_im = Image.fromarray(np.clip(out ** (1 / 2.2) * 255.0, 0, 255).astype(np.uint8), "RGB")
    diff = np.clip(np.linalg.norm(out - src, axis=-1) * 4.0, 0, 1)
    diff_im = Image.fromarray(np.clip(diff * 255.0, 0, 255).astype(np.uint8), "L").convert("RGB")
    edge_im = Image.fromarray(np.clip(maps["edge"] * 255.0, 0, 255).astype(np.uint8), "L").convert("RGB")

    panels = [src_im, out_im, diff_im, edge_im]
    labels = ["Original", "Color-follow strokes", "Diff x4", "Edge/contrast guide"]
    for im, text in zip(panels, labels):
        label_panel(im, text)
    gap = 8
    canvas = Image.new("RGB", (src_im.width * 4 + gap * 3, src_im.height), (14, 17, 22))
    x = 0
    for im in panels:
        canvas.paste(im, (x, 0))
        x += im.width + gap
    canvas.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--contact", default="")
    parser.add_argument("--metrics", default="")
    parser.add_argument("--max-size", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-stroke", type=int, default=72)
    parser.add_argument("--min-stroke", type=int, default=8)
    parser.add_argument("--density", type=float, default=0.82)
    parser.add_argument("--handmade", type=float, default=0.08)
    parser.add_argument("--style", choices=["strokes", "facets", "mixed", "brushes"], default="brushes")
    parser.add_argument("--detail-bias", type=float, default=1.0)
    args = parser.parse_args()

    rgb, alpha = load_image(args.input, args.max_size)
    if args.style == "strokes":
        out, out_alpha, maps = render_strokes(
            rgb,
            alpha,
            seed=args.seed,
            max_stroke=args.max_stroke,
            min_stroke=args.min_stroke,
            density=args.density,
            handmade=args.handmade,
        )
    elif args.style == "brushes":
        out, out_alpha, maps = render_coherent_brushes(
            rgb,
            alpha,
            seed=args.seed,
            max_stroke=args.max_stroke,
            min_stroke=args.min_stroke,
            density=args.density,
            handmade=args.handmade,
            detail_bias=args.detail_bias,
        )
    else:
        out, out_alpha, maps = render_adaptive_facets(
            rgb,
            alpha,
            seed=args.seed,
            max_stroke=args.max_stroke,
            min_stroke=args.min_stroke,
            handmade=args.handmade,
            detail_bias=args.detail_bias,
        )
        if args.style == "mixed":
            stroke_rgb, stroke_alpha, _ = render_strokes(
                rgb,
                alpha,
                seed=args.seed + 101,
                max_stroke=max(args.min_stroke * 2, int(args.max_stroke * 0.28)),
                min_stroke=args.min_stroke,
                density=args.density * 0.78,
                handmade=args.handmade,
            )
            edge = maps["edge"][..., None]
            mix = np.clip(edge * 0.55, 0.0, 0.38)
            out = out * (1.0 - mix) + stroke_rgb * mix
            out_alpha = np.maximum(out_alpha, stroke_alpha)
    save_png(args.output, out, out_alpha)
    if args.contact:
        make_contact(rgb, out, maps, args.contact)
    m = metrics(rgb, out, maps["foreground"] > 0.5)
    if args.metrics:
        Path(args.metrics).write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
