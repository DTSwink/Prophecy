"""setup_wind.py + wind_overlay.py + wind_overlay_stats.py in one editor call (no gap for anything to close the editor between them)."""
import os, unreal
d = os.path.join(unreal.Paths.project_dir(), "Exports", "Wind")
for f in ("setup_wind.py", "wind_overlay.py", "wind_overlay_stats.py"):
    src = open(os.path.join(d, f), encoding="utf-8-sig").read()
    exec(compile(src, f, "exec"), {"__name__": "__main__"})
