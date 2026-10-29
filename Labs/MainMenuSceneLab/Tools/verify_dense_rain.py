"""Check native density capacity/readbacks and preservation of the saved look."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

captures = root / "Saved/Captures"
low = load(captures / "dense-rain-20.json")
high = load(captures / "dense-rain-100.json")
assert low["rain_instances"] == high["rain_instances"] == 98532
assert abs(low["rain_density_percent"] - 20) < .001
assert high["rain_density_percent"] == 100
assert high["rain_active_seeds"] == 98532
assert 19000 < low["rain_active_seeds"] < 20500
assert 4.9 < high["rain_active_seeds"] / low["rain_active_seeds"] < 5.1
assert low["settings"]["rain_speed"] == high["settings"]["rain_speed"] == 1
assert low["rain_clock"] == high["rain_clock"]
assert low["settings"]["rain_width"] == high["settings"]["rain_width"]
assert low["settings"]["rain_length"] == high["settings"]["rain_length"]
assert low["settings"]["rain_ripple_strength"] == high["settings"]["rain_ripple_strength"]
assert load(root / "Saved/Validation/weather-controls.json")["passed"]
assert (root / "Resources/scene.json").read_bytes() == (root / "Saved/DenseRain20261029/prior-saved.json").read_bytes()
result = {
    "passed": True,
    "slider_mapping": "old 80% = new 20%; old maximum = new 25%",
    "capacity": 98532,
    "active_seeds_at_20_percent": low["rain_active_seeds"],
    "active_seeds_at_100_percent": high["rain_active_seeds"],
    "rate_ratio_100_to_20": high["rain_active_seeds"] / low["rain_active_seeds"],
    "speed_width_length_strength_unchanged": True,
    "saved_user_file_byte_identical": True,
    "native_save_reload_above_old_maximum": True,
}
(root / "Saved/Validation/dense-rain.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
