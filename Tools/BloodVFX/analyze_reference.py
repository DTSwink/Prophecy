from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = PROJECT_ROOT / "Saved" / "blood_vfx_reference"
OUTPUT_DIR = PROJECT_ROOT / "Saved" / "blood_vfx_reference_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def red_mask(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    b = rgb[..., 2].astype(np.float32)
    return (r > 48.0) & (r > g * 1.22 + 14.0) & (r > b * 1.18 + 10.0)


def bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def perimeter_estimate(mask: np.ndarray) -> int:
    if mask.size == 0:
        return 0
    h, w = mask.shape
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    center = padded[1 : h + 1, 1 : w + 1]
    edge = center & (
        (~padded[0:h, 1 : w + 1])
        | (~padded[2 : h + 2, 1 : w + 1])
        | (~padded[1 : h + 1, 0:w])
        | (~padded[1 : h + 1, 2 : w + 2])
    )
    return int(edge.sum())


def largest_component(mask: np.ndarray) -> tuple[np.ndarray, int]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best_pixels: list[tuple[int, int]] = []
    for y in range(h):
        xs = np.nonzero(mask[y] & ~seen[y])[0]
        for x0 in xs:
            if seen[y, x0]:
                continue
            stack = [(int(x0), y)]
            seen[y, x0] = True
            pixels: list[tuple[int, int]] = []
            while stack:
                x, yy = stack.pop()
                pixels.append((x, yy))
                for nx, ny in ((x - 1, yy), (x + 1, yy), (x, yy - 1), (x, yy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            if len(pixels) > len(best_pixels):
                best_pixels = pixels
    out = np.zeros_like(mask, dtype=bool)
    for x, y in best_pixels:
        out[y, x] = True
    return out, len(best_pixels)


def annotate(frame: Image.Image, mask: np.ndarray, label: str) -> Image.Image:
    rgb = np.array(frame.convert("RGB"))
    overlay = rgb.copy()
    overlay[mask] = (255, 32, 20)
    blended = (rgb.astype(np.float32) * 0.68 + overlay.astype(np.float32) * 0.32).astype(np.uint8)
    image = Image.fromarray(blended, "RGB")
    draw = ImageDraw.Draw(image)
    box = bounds(mask)
    if box:
        draw.rectangle(box, outline=(255, 225, 160), width=2)
    draw.rectangle((0, 0, image.width, 26), fill=(0, 0, 0))
    draw.text((7, 6), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return image


def main() -> None:
    frames = sorted(REFERENCE_DIR.glob("ref_*.png"))
    if not frames:
        raise SystemExit(f"No frames found in {REFERENCE_DIR}")

    metrics = []
    annotated = []
    for index, path in enumerate(frames):
        frame = Image.open(path).convert("RGB")
        rgb = np.array(frame)
        mask = red_mask(rgb)
        largest, largest_count = largest_component(mask)
        area = int(mask.sum())
        perim = perimeter_estimate(mask)
        largest_ratio = float(largest_count / area) if area else 0.0
        compactness = float((4.0 * np.pi * area) / max(perim * perim, 1)) if area else 0.0
        box = bounds(mask)
        extent = 0.0
        aspect = 0.0
        if box:
            x0, y0, x1, y1 = box
            extent = float(area / max((x1 - x0 + 1) * (y1 - y0 + 1), 1))
            aspect = float((x1 - x0 + 1) / max(y1 - y0 + 1, 1))
        metrics.append(
            {
                "frame": path.name,
                "time_seconds": round(index / 6.0, 3),
                "red_area_px": area,
                "largest_component_ratio": round(largest_ratio, 4),
                "compactness": round(compactness, 4),
                "bbox_extent": round(extent, 4),
                "bbox_aspect": round(aspect, 4),
            }
        )

        if index % 4 == 0 or area > 6000:
            label = (
                f"t={index / 6.0:4.2f}s area={area} "
                f"largest={largest_ratio:0.2f} compact={compactness:0.2f}"
            )
            annotated.append(annotate(frame, largest if largest_count else mask, label))

    tile_w, tile_h = 320, 180
    cols = 4
    rows = int(np.ceil(len(annotated) / cols))
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (0, 0, 0))
    for i, image in enumerate(annotated):
        thumb = image.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, ((i % cols) * tile_w, (i // cols) * tile_h))
    sheet.save(OUTPUT_DIR / "blood_reference_mask_sheet.jpg", quality=92)

    (OUTPUT_DIR / "blood_reference_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    nonzero = [m for m in metrics if m["red_area_px"] > 128]
    summary = {
        "frame_count": len(frames),
        "active_frame_count": len(nonzero),
        "median_largest_component_ratio": round(float(np.median([m["largest_component_ratio"] for m in nonzero])), 4)
        if nonzero
        else 0.0,
        "median_compactness": round(float(np.median([m["compactness"] for m in nonzero])), 4) if nonzero else 0.0,
        "note": "High largest-component ratio means the red pixels read as one coherent object rather than separated spray.",
    }
    (OUTPUT_DIR / "blood_reference_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
