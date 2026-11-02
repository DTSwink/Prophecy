"""Offline preview orchestrator: one bounded MCP request per render script.

Run this with ordinary Python, not inside Blender. Each request restores the
matched camera. Splitting requests avoids the add-on socket response window.
"""
import subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2]
PY=R/'Saved/Diagnostics/ImperialSpear/mcp-env/Scripts/python.exe'
CLIENT=R/'Tools/SpearAsset/mcp_client.py'
for name in ['render_seven_point_review.py','render_current_supersampled.py','render_bevel_wood_details.py','render_delivery_views.py']:
 print('Starting',name,flush=True)
 subprocess.run([str(PY),str(CLIENT),str(R/'Tools/SpearAsset'/name)],cwd=R,check=True)
print('Current preview set refreshed.')
