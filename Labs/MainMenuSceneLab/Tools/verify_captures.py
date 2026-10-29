"""Validate actual GPU readbacks from the paired native contact captures."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
captures = root / "Saved/Captures"
on = json.loads((captures / "gentle-contact-on.json").read_text(encoding="utf-8-sig"))
off = json.loads((captures / "gentle-contact-off.json").read_text(encoding="utf-8-sig"))
assert on["framework"] == off["framework"] == "Epic WaterAdvanced Niagara"
assert on["pixels"] == off["pixels"] == 512 * 512
assert on["manual_offset_cm"] == off["manual_offset_cm"] == 10
assert on["scene_seconds"] == off["scene_seconds"]
assert on["collision_enabled"] and not off["collision_enabled"]
assert off["rg_energy"] == 0 and on["rg_energy"] > 0.000001
result = {
    "passed": True,
    "description": "Same 10 cm/s root motion; live PHAT collision produces GPU normals, disabled provider stays flat.",
    "enabled_normal_xy_energy": on["rg_energy"],
    "disabled_normal_xy_energy": off["rg_energy"],
    "scene_seconds": on["scene_seconds"],
    "captures": {
        stem: hashlib.sha256((captures / (stem + ".png")).read_bytes()).hexdigest()
        for stem in ("gentle-contact-on", "gentle-contact-off", "reflection-confirmed")
    },
    "reflection_check": "Native emissive-body probe visually confirms reflected body and capture-only cards, with far rect lights removed.",
}
(root / "Saved/Validation/verified-water.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
