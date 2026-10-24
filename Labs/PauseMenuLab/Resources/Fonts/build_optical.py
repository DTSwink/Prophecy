"""Bake the approved optical axis for Slate; font weight stays 400."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root = Path(__file__).resolve().parent
for optical in range(6, 25):
    font = instantiateVariableFont(TTFont(root / "BodoniModa-variable.ttf"),
                                  {"wght": 400, "opsz": optical}, inplace=True)
    font.save(root / f"BodoniModa-Optical-{optical}.ttf")
