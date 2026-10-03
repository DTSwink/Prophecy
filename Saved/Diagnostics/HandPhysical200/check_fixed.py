import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
p=Path(__file__).resolve().parent
capture=json.loads((p/'fixed_forearm.json').read_text(encoding='utf8'))
rows={r['tick']:r for r in capture['rows']}
def angle(a,b):
 return float(np.degrees((Rotation.from_quat(a['q'])*Rotation.from_quat(b['q']).inv()).magnitude()))
result={'reason':capture['reason'],'right_hand_error_degrees':{t:angle(rows[t]['bodies']['hand_r']['transform'],rows[t]['targets']['hand_r']['target']) for t in range(199,205)}}
(p/'fixed-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
