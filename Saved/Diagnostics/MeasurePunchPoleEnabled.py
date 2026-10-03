from pathlib import Path
s=Path('Saved/Diagnostics/MeasurePunchPole.py').read_text().replace("'PunchKneeBaseline-live.json'", "'PunchPole-enabled-live.json'")
exec(s)
