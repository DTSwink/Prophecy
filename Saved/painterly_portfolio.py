import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


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


def load_image(path, max_size=0):
    path = Path(path)
    if path.suffix.lower() == ".exr":
        w, h = probe_size(path)
        vf = []
        if max_size and max(w, h) > max_size:
            scale = max_size / max(w, h)
            w = max(1, int(round(w * scale)))
            h = max(1, int(round(h * scale)))
            vf = ["-vf", f"scale={w}:{h}:flags=lanczos"]
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


def save_png(path, rgb, alpha=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb8 = np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
    if alpha is None:
        Image.fromarray(rgb8, "RGB").save(path)
    else:
        a8 = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
        Image.fromarray(np.dstack([rgb8, a8]), "RGBA").save(path)


def load_rgb_pil(path):
    return Image.open(path).convert("RGB")


def to_rgb8(rgb):
    return np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def blur_float(arr, radius):
    if radius <= 0:
        return arr.astype(np.float32, copy=True)
    arr = arr.astype(np.float32, copy=False)
    mn = float(np.min(arr))
    mx = float(np.max(arr))
    if mx - mn < 1e-8:
        return arr.copy()
    im = Image.fromarray(np.clip((arr - mn) / (mx - mn) * 255.0, 0, 255).astype(np.uint8), "L")
    out = np.asarray(im.filter(ImageFilter.GaussianBlur(float(radius))), dtype=np.float32) / 255.0
    return out * (mx - mn) + mn


def box_blur_float(arr, radius):
    if radius <= 0:
        return arr.astype(np.float32, copy=True)
    arr = arr.astype(np.float32, copy=False)
    mn = float(np.min(arr))
    mx = float(np.max(arr))
    if mx - mn < 1e-8:
        return arr.copy()
    im = Image.fromarray(np.clip((arr - mn) / (mx - mn) * 255.0, 0, 255).astype(np.uint8), "L")
    out = np.asarray(im.filter(ImageFilter.BoxBlur(float(radius))), dtype=np.float32) / 255.0
    return out * (mx - mn) + mn


def rgb_to_hsv(rgb):
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
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


def luma(rgb):
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def gradients(arr):
    dx = np.zeros_like(arr, dtype=np.float32)
    dy = np.zeros_like(arr, dtype=np.float32)
    dx[:, 1:-1] = 0.5 * (arr[:, 2:] - arr[:, :-2])
    dx[:, 0] = arr[:, 1] - arr[:, 0]
    dx[:, -1] = arr[:, -1] - arr[:, -2]
    dy[1:-1, :] = 0.5 * (arr[2:, :] - arr[:-2, :])
    dy[0, :] = arr[1, :] - arr[0, :]
    dy[-1, :] = arr[-1, :] - arr[-2, :]
    return dx, dy


def structure_tensor_angle(rgb, sigma):
    fx = np.zeros(rgb.shape[:2], dtype=np.float32)
    fy = np.zeros(rgb.shape[:2], dtype=np.float32)
    fxy = np.zeros(rgb.shape[:2], dtype=np.float32)
    for c in range(3):
        dx, dy = gradients(rgb[..., c])
        fx += dx * dx
        fy += dy * dy
        fxy += dx * dy
    fx = blur_float(fx, sigma)
    fy = blur_float(fy, sigma)
    fxy = blur_float(fxy, sigma)
    grad_angle = 0.5 * np.arctan2(2.0 * fxy, fx - fy + 1e-6)
    return grad_angle + math.pi * 0.5


def edge_mask(rgb, sigma=1.0, strength=6.0):
    y = luma(rgb)
    y = blur_float(y, sigma)
    dx, dy = gradients(y)
    g = np.sqrt(dx * dx + dy * dy)
    hi = np.percentile(g, 96.0)
    lo = np.percentile(g, 62.0)
    denom = max(hi - lo, 1e-5)
    e = np.clip((g - lo) / denom, 0.0, 1.0)
    return np.clip(e * strength / 6.0, 0.0, 1.0)


def preserve_mask(rgb, alpha):
    mx = np.max(rgb, axis=-1)
    mn = np.min(rgb, axis=-1)
    return (alpha < 0.02) | (mx < 0.10) | (mn > 0.985)


def finish_effect(src, effect, alpha, edge_strength=0.0, preserve=True):
    out = np.clip(effect, 0.0, 1.0)
    if edge_strength > 0:
        e = edge_mask(src, sigma=0.8, strength=6.0)
        out = out * (1.0 - edge_strength * e[..., None])
    if preserve:
        keep = preserve_mask(src, alpha)
        out = np.where(keep[..., None], src, out)
    return np.clip(out, 0.0, 1.0)


def quantize_hsv(rgb, h_levels=24, s_levels=8, v_levels=8, blend=1.0):
    hsv = rgb_to_hsv(rgb)
    q = hsv.copy()
    q[..., 0] = (np.floor(q[..., 0] * h_levels + 0.5) % h_levels) / h_levels
    q[..., 1] = np.floor(q[..., 1] * (s_levels - 1) + 0.5) / max(s_levels - 1, 1)
    q[..., 2] = np.floor(q[..., 2] * (v_levels - 1) + 0.5) / max(v_levels - 1, 1)
    qr = hsv_to_rgb(q)
    return rgb * (1.0 - blend) + qr * blend


def shift_edge(arr, dx, dy):
    h, w = arr.shape[:2]
    pad = max(abs(dx), abs(dy), 1)
    pad_spec = ((pad, pad), (pad, pad))
    if arr.ndim == 3:
        pad_spec += ((0, 0),)
    p = np.pad(arr, pad_spec, mode="edge")
    return p[pad + dy : pad + dy + h, pad + dx : pad + dx + w]


def bilateral_abstraction(rgb, alpha, radius, range_sigma, iterations, h_levels, v_levels, edge_strength):
    out = rgb.copy()
    offsets = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (-1, 1),
        (1, -1),
        (-1, -1),
    ]
    for it in range(iterations):
        step = max(1, int(round(radius * (0.35 + 0.65 * (it + 1) / max(iterations, 1)))))
        accum = out * 1.7
        weight_sum = np.full(out.shape[:2], 1.7, dtype=np.float32)
        for ox, oy in offsets:
            dx = ox * step
            dy = oy * step
            nb = shift_edge(out, dx, dy)
            color_d2 = np.sum((nb - out) * (nb - out), axis=-1)
            spatial = math.exp(-(dx * dx + dy * dy) / max(2.0 * radius * radius, 1e-5))
            wgt = spatial * np.exp(-color_d2 / max(2.0 * range_sigma * range_sigma, 1e-5))
            accum += nb * wgt[..., None]
            weight_sum += wgt
        out = accum / np.maximum(weight_sum[..., None], 1e-5)
    out = quantize_hsv(out, h_levels=h_levels, s_levels=8, v_levels=v_levels, blend=0.72)
    return finish_effect(rgb, out, alpha, edge_strength=edge_strength)


def xdog_abstraction(rgb, alpha, blur_radius, levels, edge_strength, contrast):
    base = rgb.copy()
    for _ in range(3):
        base = bilateral_abstraction(
            base,
            alpha,
            radius=max(1, blur_radius),
            range_sigma=0.22,
            iterations=1,
            h_levels=levels,
            v_levels=max(4, levels // 2),
            edge_strength=0.0,
        )
    y = luma(rgb)
    g1 = blur_float(y, max(0.6, blur_radius * 0.30))
    g2 = blur_float(y, max(1.2, blur_radius * 0.95))
    dog = g1 - 0.96 * g2
    ink = 1.0 - np.clip((dog + 0.018) * contrast + 0.5, 0.0, 1.0)
    grad = edge_mask(rgb, sigma=0.8, strength=5.0)
    edge = np.clip(0.65 * ink + 0.55 * grad, 0.0, 1.0)
    out = base * (1.0 - edge_strength * edge[..., None])
    return finish_effect(rgb, out, alpha, edge_strength=0.0)


def oil_mode_filter(rgb, alpha, radius, h_bins, v_bins, sat_floor, blend, edge_strength):
    hsv = rgb_to_hsv(rgb)
    hbin = np.floor(hsv[..., 0] * h_bins).astype(np.int32) % h_bins
    vbin = np.clip(np.floor(hsv[..., 2] * v_bins).astype(np.int32), 0, v_bins - 1)
    low_sat = hsv[..., 1] < sat_floor
    key = hbin + h_bins * vbin
    key = np.where(low_sat, h_bins * v_bins + vbin, key)
    n_bins = h_bins * v_bins + v_bins

    best_count = np.full(rgb.shape[:2], -1.0, dtype=np.float32)
    best_rgb = rgb.copy()
    for k in range(n_bins):
        mask = (key == k).astype(np.float32)
        if float(mask.mean()) < 0.0001:
            continue
        count = box_blur_float(mask, radius)
        sums = []
        for c in range(3):
            sums.append(box_blur_float(rgb[..., c] * mask, radius))
        avg = np.stack(sums, axis=-1) / np.maximum(count[..., None], 1e-5)
        take = count > best_count
        best_count = np.where(take, count, best_count)
        best_rgb = np.where(take[..., None], avg, best_rgb)

    out = rgb * (1.0 - blend) + best_rgb * blend
    out = quantize_hsv(out, h_levels=max(8, h_bins), s_levels=7, v_levels=max(4, v_bins + 3), blend=0.22)
    return finish_effect(rgb, out, alpha, edge_strength=edge_strength)


def bilinear_sample(img, x, y):
    h, w = img.shape[:2]
    x = np.clip(x, 0.0, w - 1.001)
    y = np.clip(y, 0.0, h - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]
    a = img[y0, x0]
    b = img[y0, x1]
    c = img[y1, x0]
    d = img[y1, x1]
    return (a * (1.0 - wx) + b * wx) * (1.0 - wy) + (c * (1.0 - wx) + d * wx) * wy


def flow_smooth(rgb, alpha, length, samples, tensor_sigma, iterations, quant, edge_strength):
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    angle = structure_tensor_angle(rgb, tensor_sigma)
    vx = np.cos(angle).astype(np.float32)
    vy = np.sin(angle).astype(np.float32)
    out = rgb.copy()
    half = max(1, samples // 2)
    for _ in range(iterations):
        accum = out.copy() * 1.2
        weight_sum = np.full((h, w, 1), 1.2, dtype=np.float32)
        for i in range(1, half + 1):
            dist = length * i / half
            weight = math.exp(-0.5 * (i / max(half * 0.62, 1e-5)) ** 2)
            accum += bilinear_sample(out, xx + vx * dist, yy + vy * dist) * weight
            accum += bilinear_sample(out, xx - vx * dist, yy - vy * dist) * weight
            weight_sum += 2.0 * weight
        out = accum / weight_sum
    if quant > 0:
        out = quantize_hsv(out, h_levels=quant, s_levels=8, v_levels=max(5, quant // 2), blend=0.45)
    return finish_effect(rgb, out, alpha, edge_strength=edge_strength)


def hybrid_flow_oil(rgb, alpha, flow_length, oil_radius, h_bins, edge_strength):
    flowed = flow_smooth(
        rgb,
        alpha,
        length=flow_length,
        samples=9,
        tensor_sigma=max(2.0, flow_length * 0.35),
        iterations=2,
        quant=0,
        edge_strength=0.0,
    )
    out = oil_mode_filter(
        flowed,
        alpha,
        radius=oil_radius,
        h_bins=h_bins,
        v_bins=4,
        sat_floor=0.10,
        blend=0.88,
        edge_strength=0.0,
    )
    return finish_effect(rgb, out, alpha, edge_strength=edge_strength)


def local_mean(rgb, x, y, radius):
    h, w = rgb.shape[:2]
    x = float(np.clip(x, 0, w - 1))
    y = float(np.clip(y, 0, h - 1))
    x0 = max(0, int(round(x - radius)))
    x1 = min(w, int(round(x + radius + 1)))
    y0 = max(0, int(round(y - radius)))
    y1 = min(h, int(round(y + radius + 1)))
    if x1 <= x0 or y1 <= y0:
        return rgb[int(round(y)), int(round(x))]
    return rgb[y0:y1, x0:x1].mean(axis=(0, 1))


def brush_mask(length, width, roughness, rng):
    length = max(6, int(round(length)))
    width = max(3, int(round(width)))
    yy, xx = np.mgrid[0:width, 0:length].astype(np.float32)
    x = (xx / max(length - 1, 1)) * 2.0 - 1.0
    y = (yy / max(width - 1, 1)) * 2.0 - 1.0
    body = np.clip(1.0 - (np.abs(x) ** 2.8 + np.abs(y) ** 2.0), 0.0, 1.0)
    body = np.power(body, 0.45)
    noise = rng.random((width, length), dtype=np.float32)
    bristles = blur_float(noise, max(0.7, width * 0.09))
    dry = np.clip((bristles - (0.42 + roughness * 0.16)) / max(0.25, 0.48 - roughness * 0.10), 0.0, 1.0)
    mask = body * (0.62 + 0.38 * dry)
    mask[:, : max(1, length // 12)] *= np.linspace(0.15, 1.0, max(1, length // 12))[None, :]
    mask[:, -max(1, length // 10) :] *= np.linspace(1.0, 0.08, max(1, length // 10))[None, :]
    return Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L")


def draw_stroke(canvas, color, cx, cy, length, width, angle, opacity, roughness, rng):
    mask = brush_mask(length, width, roughness, rng)
    deg = angle * 180.0 / math.pi
    mask = mask.rotate(deg, resample=Image.Resampling.BICUBIC, expand=True)
    alpha = mask.point(lambda p: int(p * opacity))
    patch = Image.new("RGBA", mask.size, tuple(color) + (0,))
    patch.putalpha(alpha)
    x = int(round(cx - mask.size[0] * 0.5))
    y = int(round(cy - mask.size[1] * 0.5))
    canvas.alpha_composite(patch, dest=(x, y))


def soft_patch_mask(length, width, roughness, rng):
    length = max(6, int(round(length)))
    width = max(4, int(round(width)))
    yy, xx = np.mgrid[0:width, 0:length].astype(np.float32)
    x = (xx / max(length - 1, 1)) * 2.0 - 1.0
    y = (yy / max(width - 1, 1)) * 2.0 - 1.0
    body = np.clip(1.0 - (np.abs(x) ** 3.8 + np.abs(y) ** 3.2), 0.0, 1.0)
    body = np.power(body, 0.34)
    if roughness <= 0.02:
        edge = 1.0
    else:
        n = blur_float(rng.random((width, length), dtype=np.float32), max(1.2, width * 0.20))
        edge = 0.92 + 0.08 * n
    mask = body * edge
    if roughness > 0:
        wobble = blur_float(rng.random((width, length), dtype=np.float32), max(1.5, width * 0.32))
        mask *= np.clip(0.88 + wobble * (0.08 + roughness * 0.12), 0.0, 1.0)
    im = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L")
    return im.filter(ImageFilter.GaussianBlur(max(0.25, width * 0.025)))


def draw_soft_patch(canvas, color, cx, cy, length, width, angle, opacity, roughness, rng):
    mask = soft_patch_mask(length, width, roughness, rng)
    mask = mask.rotate(angle * 180.0 / math.pi, resample=Image.Resampling.BICUBIC, expand=True)
    alpha = mask.point(lambda p: int(p * opacity))
    patch = Image.new("RGBA", mask.size, tuple(color) + (0,))
    patch.putalpha(alpha)
    x = int(round(cx - mask.size[0] * 0.5))
    y = int(round(cy - mask.size[1] * 0.5))
    canvas.alpha_composite(patch, dest=(x, y))


def patch_dab_renderer(
    rgb,
    alpha,
    seed,
    base_length,
    density,
    roughness,
    color_radius,
    flow_mix,
    opacity,
    palette,
    edge_strength,
):
    h, w = rgb.shape[:2]
    rng = np.random.default_rng(seed)
    if palette == "hybrid":
        base = hybrid_flow_oil(
            rgb,
            alpha,
            flow_length=max(7.0, base_length * 0.22),
            oil_radius=max(6.0, color_radius * 0.65),
            h_bins=12,
            edge_strength=0.0,
        )
    elif palette == "oil":
        base = oil_mode_filter(
            rgb,
            alpha,
            radius=max(5.0, color_radius * 0.65),
            h_bins=13,
            v_bins=4,
            sat_floor=0.10,
            blend=0.86,
            edge_strength=0.0,
        )
    else:
        base = flow_smooth(
            rgb,
            alpha,
            length=max(5.0, base_length * 0.20),
            samples=7,
            tensor_sigma=max(2.0, base_length * 0.08),
            iterations=2,
            quant=16,
            edge_strength=0.0,
        )

    color_src = quantize_hsv(base, h_levels=16, s_levels=8, v_levels=7, blend=0.32)
    rgba = np.dstack([to_rgb8(base), np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)])
    canvas = Image.fromarray(rgba, "RGBA")
    angle = structure_tensor_angle(rgb, max(2.0, base_length * 0.12))
    fg = ~preserve_mask(rgb, alpha)

    pass_defs = [
        (1.00, 0.48, opacity),
        (0.58, 0.54, opacity * 0.82),
        (0.32, 0.62, opacity * 0.64),
    ]
    for length_mul, width_mul, pass_opacity in pass_defs:
        p_len = max(6.0, base_length * length_mul)
        spacing = max(4, int(round(p_len * density)))
        xs = np.arange(0, w, spacing)
        ys = np.arange(0, h, spacing)
        centers = [(x + rng.uniform(0, spacing), y + rng.uniform(0, spacing)) for y in ys for x in xs]
        rng.shuffle(centers)
        for cx, cy in centers:
            ix = int(np.clip(cx, 0, w - 1))
            iy = int(np.clip(cy, 0, h - 1))
            if not fg[iy, ix]:
                continue
            a = float(angle[iy, ix] + rng.uniform(-0.70, 0.70))
            shift = rng.normal(0.0, flow_mix * p_len)
            sx = float(np.clip(cx + math.cos(a) * shift, 0, w - 1))
            sy = float(np.clip(cy + math.sin(a) * shift, 0, h - 1))
            col = local_mean(color_src, sx, sy, max(1.0, color_radius * length_mul))
            col = np.clip(col * 255.0 + 0.5, 0, 255).astype(np.uint8)
            length = p_len * rng.uniform(0.78, 1.30)
            width = max(4.0, p_len * width_mul * rng.uniform(0.42, 0.78))
            draw_soft_patch(canvas, tuple(int(v) for v in col), cx, cy, length, width, a, pass_opacity, roughness, rng)

    out = np.asarray(canvas).astype(np.float32) / 255.0
    return finish_effect(rgb, out[..., :3], alpha, edge_strength=edge_strength)


def stroke_renderer(rgb, alpha, seed, base_length, density, roughness, mode, edge_strength):
    h, w = rgb.shape[:2]
    rng = np.random.default_rng(seed)
    angle = structure_tensor_angle(rgb, max(2.0, base_length * 0.16))
    fg = ~preserve_mask(rgb, alpha)
    base = flow_smooth(
        rgb,
        alpha,
        length=max(4, base_length * 0.24),
        samples=5,
        tensor_sigma=max(1.5, base_length * 0.10),
        iterations=1,
        quant=0,
        edge_strength=0.0,
    )
    rgba = np.dstack([to_rgb8(base), np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)])
    canvas = Image.fromarray(rgba, "RGBA")
    passes = [
        (base_length, 0.55, 0.84),
        (base_length * 0.55, 0.42, 0.74),
        (base_length * 0.26, 0.28, 0.62),
    ]
    if mode == "dabs":
        passes = [
            (base_length * 0.58, 0.70, 0.78),
            (base_length * 0.34, 0.56, 0.70),
            (base_length * 0.18, 0.42, 0.54),
        ]

    for p_len, width_mul, opacity in passes:
        spacing = max(4, int(round(p_len * density)))
        xs = np.arange(0, w, spacing)
        ys = np.arange(0, h, spacing)
        centers = [(x + rng.uniform(0, spacing), y + rng.uniform(0, spacing)) for y in ys for x in xs]
        rng.shuffle(centers)
        for cx, cy in centers:
            ix = int(np.clip(cx, 0, w - 1))
            iy = int(np.clip(cy, 0, h - 1))
            if not fg[iy, ix]:
                continue
            jitter = rng.uniform(-0.45, 0.45) if mode == "dabs" else rng.uniform(-0.20, 0.20)
            a = float(angle[iy, ix] + jitter)
            length = p_len * rng.uniform(0.72, 1.24)
            width = max(3.0, p_len * width_mul * rng.uniform(0.28, 0.52))
            if mode == "dabs":
                length *= rng.uniform(0.45, 0.82)
                width *= rng.uniform(0.70, 1.15)
            col = local_mean(rgb, cx, cy, max(1.0, width * 0.40))
            col = np.clip(col * 255.0 + 0.5, 0, 255).astype(np.uint8)
            draw_stroke(canvas, tuple(int(v) for v in col), cx, cy, length, width, a, opacity, roughness, rng)

    out = np.asarray(canvas).astype(np.float32) / 255.0
    return finish_effect(rgb, out[..., :3], alpha, edge_strength=edge_strength)


def scale_params(params, scale):
    out = dict(params)
    for k in [
        "radius",
        "blur_radius",
        "length",
        "flow_length",
        "oil_radius",
        "base_length",
        "tensor_sigma",
    ]:
        if k in out:
            out[k] = max(1.0, float(out[k]) * scale)
    return out


VARIANTS = [
    {
        "name": "wog_bilateral_xdog_soft",
        "family": "Winnemoller_Bilateral_XDoG",
        "fn": "xdog",
        "params": {"blur_radius": 7.0, "levels": 14, "edge_strength": 0.14, "contrast": 6.5},
    },
    {
        "name": "wog_bilateral_xdog_bold",
        "family": "Winnemoller_Bilateral_XDoG",
        "fn": "xdog",
        "params": {"blur_radius": 10.0, "levels": 10, "edge_strength": 0.23, "contrast": 8.5},
    },
    {
        "name": "oil_hv_mode_small",
        "family": "OilPaint_Mode_Filter",
        "fn": "oil",
        "params": {"radius": 7.0, "h_bins": 18, "v_bins": 4, "sat_floor": 0.08, "blend": 0.82, "edge_strength": 0.08},
    },
    {
        "name": "oil_hv_mode_large",
        "family": "OilPaint_Mode_Filter",
        "fn": "oil",
        "params": {"radius": 13.0, "h_bins": 12, "v_bins": 4, "sat_floor": 0.10, "blend": 0.92, "edge_strength": 0.13},
    },
    {
        "name": "oil_hv_mode_chunky",
        "family": "OilPaint_Mode_Filter",
        "fn": "oil",
        "params": {"radius": 20.0, "h_bins": 10, "v_bins": 3, "sat_floor": 0.12, "blend": 0.94, "edge_strength": 0.16},
    },
    {
        "name": "oil_hv_mode_reference_mid",
        "family": "OilPaint_Mode_Filter",
        "fn": "oil",
        "params": {"radius": 16.0, "h_bins": 16, "v_bins": 5, "sat_floor": 0.09, "blend": 0.88, "edge_strength": 0.07},
    },
    {
        "name": "kang_flow_smooth_short",
        "family": "Flow_Based_Abstraction",
        "fn": "flow",
        "params": {"length": 8.0, "samples": 7, "tensor_sigma": 3.0, "iterations": 2, "quant": 18, "edge_strength": 0.07},
    },
    {
        "name": "kang_flow_smooth_long",
        "family": "Flow_Based_Abstraction",
        "fn": "flow",
        "params": {"length": 16.0, "samples": 11, "tensor_sigma": 5.0, "iterations": 3, "quant": 14, "edge_strength": 0.11},
    },
    {
        "name": "hybrid_flow_oil_soft_islands",
        "family": "Flow_Then_Oil_Mode",
        "fn": "hybrid",
        "params": {"flow_length": 9.0, "oil_radius": 8.0, "h_bins": 16, "edge_strength": 0.08},
    },
    {
        "name": "hybrid_flow_oil_broad_islands",
        "family": "Flow_Then_Oil_Mode",
        "fn": "hybrid",
        "params": {"flow_length": 15.0, "oil_radius": 14.0, "h_bins": 12, "edge_strength": 0.12},
    },
    {
        "name": "hybrid_flow_oil_chunky_canvas",
        "family": "Flow_Then_Oil_Mode",
        "fn": "hybrid",
        "params": {"flow_length": 21.0, "oil_radius": 20.0, "h_bins": 10, "edge_strength": 0.14},
    },
    {
        "name": "hybrid_flow_oil_reference_mid",
        "family": "Flow_Then_Oil_Mode",
        "fn": "hybrid",
        "params": {"flow_length": 13.0, "oil_radius": 16.0, "h_bins": 15, "edge_strength": 0.075},
    },
    {
        "name": "target_patch_oil_medium",
        "family": "Soft_Patch_Dabs",
        "fn": "dab_patch",
        "params": {
            "base_length": 54.0,
            "density": 0.46,
            "roughness": 0.26,
            "color_radius": 18.0,
            "flow_mix": 0.70,
            "opacity": 0.68,
            "palette": "oil",
            "edge_strength": 0.02,
        },
    },
    {
        "name": "target_patch_hybrid_broad",
        "family": "Soft_Patch_Dabs",
        "fn": "dab_patch",
        "params": {
            "base_length": 82.0,
            "density": 0.36,
            "roughness": 0.22,
            "color_radius": 26.0,
            "flow_mix": 0.95,
            "opacity": 0.62,
            "palette": "hybrid",
            "edge_strength": 0.025,
        },
    },
    {
        "name": "target_patch_hybrid_dense",
        "family": "Soft_Patch_Dabs",
        "fn": "dab_patch",
        "params": {
            "base_length": 64.0,
            "density": 0.32,
            "roughness": 0.34,
            "color_radius": 20.0,
            "flow_mix": 0.75,
            "opacity": 0.58,
            "palette": "hybrid",
            "edge_strength": 0.02,
        },
    },
    {
        "name": "target_clean_swatches_medium",
        "family": "Soft_Patch_Dabs",
        "fn": "dab_patch",
        "params": {
            "base_length": 58.0,
            "density": 0.54,
            "roughness": 0.0,
            "color_radius": 22.0,
            "flow_mix": 0.42,
            "opacity": 0.42,
            "palette": "oil",
            "edge_strength": 0.015,
        },
    },
    {
        "name": "target_clean_swatches_broad",
        "family": "Soft_Patch_Dabs",
        "fn": "dab_patch",
        "params": {
            "base_length": 92.0,
            "density": 0.44,
            "roughness": 0.0,
            "color_radius": 30.0,
            "flow_mix": 0.55,
            "opacity": 0.36,
            "palette": "hybrid",
            "edge_strength": 0.015,
        },
    },
    {
        "name": "litwinowicz_impressionist_dabs",
        "family": "Impressionist_Stroke_Dabs",
        "fn": "stroke",
        "params": {"base_length": 28.0, "density": 0.86, "roughness": 0.42, "mode": "dabs", "edge_strength": 0.03},
    },
    {
        "name": "litwinowicz_chunky_dabs",
        "family": "Impressionist_Stroke_Dabs",
        "fn": "stroke",
        "params": {"base_length": 48.0, "density": 0.58, "roughness": 0.56, "mode": "dabs", "edge_strength": 0.04},
    },
    {
        "name": "hertzmann_curved_strokes",
        "family": "MultiScale_Curved_Strokes",
        "fn": "stroke",
        "params": {"base_length": 54.0, "density": 0.74, "roughness": 0.24, "mode": "curved", "edge_strength": 0.02},
    },
    {
        "name": "hertzmann_long_dry_strokes",
        "family": "MultiScale_Curved_Strokes",
        "fn": "stroke",
        "params": {"base_length": 88.0, "density": 0.62, "roughness": 0.38, "mode": "curved", "edge_strength": 0.03},
    },
]


def render_variant(rgb, alpha, variant, scale, seed):
    params = scale_params(variant["params"], scale)
    fn = variant["fn"]
    if fn == "xdog":
        return xdog_abstraction(rgb, alpha, **params)
    if fn == "oil":
        return oil_mode_filter(rgb, alpha, **params)
    if fn == "flow":
        return flow_smooth(rgb, alpha, **params)
    if fn == "hybrid":
        return hybrid_flow_oil(rgb, alpha, **params)
    if fn == "dab_patch":
        return patch_dab_renderer(rgb, alpha, seed=seed, **params)
    if fn == "stroke":
        return stroke_renderer(rgb, alpha, seed=seed, **params)
    raise ValueError(f"Unknown variant function: {fn}")


def make_reference_crop(project_root):
    split = Path(r"C:\Users\singerie\Documents\Cursor\paint\checkpoints\live_paint\coarse_unlit_brush_body\split_capture_coarse_unlit_brush_body.png")
    out = project_root / "Saved" / "monkey_reference_modified_crop.png"
    if out.exists():
        return out
    if not split.exists():
        return None
    im = Image.open(split).convert("RGBA")
    im.crop((963, 0, 1545, 896)).save(out)
    return out


def non_black_bbox(im, threshold=10):
    arr = np.asarray(im.convert("RGB"))
    mask = np.max(arr, axis=-1) > threshold
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return (0, 0, im.width, im.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def align_reference_to_source(reference_path, source_rgb, out_path):
    src_im = Image.fromarray(to_rgb8(source_rgb), "RGB")
    ref_im = load_rgb_pil(reference_path)
    canvas = ref_im.resize(src_im.size, Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    arr = np.asarray(canvas).astype(np.float32) / 255.0
    return arr, out_path


def reference_metrics(src, out, ref):
    src_mask = np.max(src, axis=-1) > 0.08
    ref_mask = np.max(ref, axis=-1) > 0.08
    mask = src_mask | ref_mask
    if not np.any(mask):
        mask = np.ones(src.shape[:2], dtype=bool)
    src_err = float(np.mean(np.abs(src[mask] - ref[mask])) * 255.0)
    out_err = float(np.mean(np.abs(out[mask] - ref[mask])) * 255.0)
    move = float(np.mean(np.abs(out[mask] - src[mask])) * 255.0)
    improvement = 0.0 if src_err <= 1e-6 else (src_err - out_err) / src_err
    return {
        "target_error_255": round(out_err, 3),
        "original_error_255": round(src_err, 3),
        "mean_move_from_original_255": round(move, 3),
        "target_error_improvement": round(improvement, 4),
    }


def image_for_sheet(path, max_h=300):
    im = Image.open(path).convert("RGB")
    if im.height > max_h:
        scale = max_h / im.height
        im = im.resize((max(1, int(round(im.width * scale))), max_h), Image.Resampling.LANCZOS)
    return im


def make_sheet(items, out_path, columns=4, max_h=300):
    thumbs = [(label, image_for_sheet(path, max_h=max_h)) for label, path in items]
    label_h = 26
    pad = 12
    cols = min(columns, len(thumbs))
    rows = int(math.ceil(len(thumbs) / cols))
    cell_w = max(im.width for _, im in thumbs)
    cell_h = max(im.height for _, im in thumbs)
    sheet = Image.new("RGB", (pad + cols * (cell_w + pad), pad + rows * (cell_h + label_h + pad)), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(thumbs):
        x = pad + (i % cols) * (cell_w + pad)
        y = pad + (i // cols) * (cell_h + label_h + pad)
        draw.text((x, y), label, fill=(238, 238, 238))
        sheet.paste(im, (x, y + label_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=95)


def run_set(label, input_path, out_dir, max_size, seed, include_reference=False, reference_path=None):
    rgb, alpha = load_image(input_path, max_size=max_size)
    h, w = rgb.shape[:2]
    scale = max(h, w) / 896.0
    target = out_dir / label
    target.mkdir(parents=True, exist_ok=True)
    save_png(target / "_original.png", rgb, alpha)

    metadata = {
        "input": str(input_path),
        "size": [w, h],
        "scale_reference_max_896": scale,
        "outputs": [],
    }
    sheet_items = [("Original", target / "_original.png")]

    reference_rgb = None
    reference_file = None
    if reference_path:
        reference_rgb, reference_file = align_reference_to_source(reference_path, rgb, target / "_target_aligned.png")
        sheet_items.append(("Target", reference_file))
    elif include_reference:
        ref = make_reference_crop(Path.cwd())
        if ref and ref.exists():
            sheet_items.append(("Reference", ref))

    for idx, variant in enumerate(VARIANTS):
        out = render_variant(rgb, alpha, variant, scale=scale, seed=seed + idx * 97)
        path = target / f"{idx + 1:02d}_{variant['name']}.png"
        save_png(path, out, alpha)
        diff = float(np.mean(np.abs(out - rgb)) * 255.0)
        row = {
            "name": variant["name"],
            "family": variant["family"],
            "path": str(path),
            "mean_rgb_delta_255": round(diff, 3),
            "params": scale_params(variant["params"], scale),
        }
        label_text = f"{idx + 1:02d} {variant['name']}"
        if reference_rgb is not None:
            ref_metrics = reference_metrics(rgb, out, reference_rgb)
            row.update(ref_metrics)
            label_text = f"{idx + 1:02d} {variant['name']} e{ref_metrics['target_error_255']:.1f}"
            print(
                f"{label}: {idx + 1:02d}_{variant['name']} "
                f"move={diff:.2f} target_err={ref_metrics['target_error_255']:.2f} "
                f"improve={ref_metrics['target_error_improvement']:.3f}"
            )
        else:
            print(f"{label}: {idx + 1:02d}_{variant['name']} diff={diff:.2f}")
        metadata["outputs"].append(row)
        sheet_items.append((label_text, path))

    make_sheet(sheet_items, out_dir / f"{label}_portfolio_contact.png", columns=4, max_h=300)
    with (target / "_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    return metadata


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--monkey", default=r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\monkey_original_crop.png")
    p.add_argument("--correct-source", default=r"C:\Users\singerie\AppData\Local\Temp\codex-clipboard-c365d762-c234-4f63-80ed-1004b1f2429c.png")
    p.add_argument("--correct-target", default=r"C:\Users\singerie\AppData\Local\Temp\codex-clipboard-7529cebc-44c5-46a1-b973-eb74c1a95bf8.png")
    p.add_argument("--ue", default=r"C:\Users\singerie\Documents\Cursor\paint\hehe.EXR")
    p.add_argument("--out", default=r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\painterly_portfolio")
    p.add_argument("--ue-max", type=int, default=1024)
    p.add_argument("--monkey-max", type=int, default=0)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--only", choices=["all", "monkey", "correct", "ue"], default="all")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_meta = {"variants": VARIANTS, "sets": []}
    if args.only in ("all", "monkey"):
        all_meta["sets"].append(
            run_set(
                "monkey",
                Path(args.monkey),
                out_dir,
                max_size=args.monkey_max,
                seed=args.seed,
                include_reference=True,
            )
        )
    if args.only in ("all", "correct"):
        all_meta["sets"].append(
            run_set(
                "correct_monkey",
                Path(args.correct_source),
                out_dir,
                max_size=args.monkey_max,
                seed=args.seed,
                include_reference=False,
                reference_path=Path(args.correct_target),
            )
        )
    if args.only in ("all", "ue"):
        all_meta["sets"].append(
            run_set(
                f"ue_{args.ue_max if args.ue_max else 'full'}",
                Path(args.ue),
                out_dir,
                max_size=args.ue_max,
                seed=args.seed + 7000,
                include_reference=False,
            )
        )
    with (out_dir / "_portfolio_index.json").open("w", encoding="utf-8") as f:
        json.dump(all_meta, f, indent=2)
    print(out_dir)


if __name__ == "__main__":
    main()
