"""Frozen transfer starts for the actual UE robot/NNE contact regression."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/Diagnostics/RobotLocomotion20261026'
SOURCE = ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/fresh-100'
basis = R.from_euler('z', -90, degrees=True)

def convert(state):
    ue = state.copy()
    ue[:, :3] = basis.apply(state[:, :3])*100
    ue[:, 3:7] = (basis*R.from_quat(state[:, 3:7])).as_quat()
    ue[:, 7:10] = basis.apply(state[:, 7:10])*100
    ue[:, 10:13] = basis.apply(state[:, 10:13])
    return ue.tolist()

starts = np.load(SOURCE/'starts.npz')
rows = []
for i, row in enumerate(json.loads((SOURCE/'manifest.json').read_text())['rows']):
    assert row['arm_enabled'] == [1, 1]
    rows.append(dict(case=i, clanker=False, states=convert(starts['states'][i]),
        phase=starts['phase'][i].tolist(), metadata=row))
for row in json.loads((OUT/'transfer-audit/directions.json').read_text()):
    seed = np.load(OUT/f"native-case{row['case']}.npz")
    angle = np.deg2rad(row['direction_deg'])
    direction = basis.apply([np.cos(angle), np.sin(angle), 0]).tolist()
    rows.append(dict(case=row['case']*8+row['direction_deg']//45, clanker=True,
        states=convert(seed['states'][420]), phase=seed['phases'][420].tolist(),
        direction=direction, native_success=row['native']['first_fall_tick'] is None
            and row['native']['command_travel_cm'] > 100))
(OUT/'contact-transfer-vectors.json').write_text(json.dumps(rows), encoding='utf-8')
print(f'Prepared {len(rows)} frozen cases; no new seeds or tuning.')
