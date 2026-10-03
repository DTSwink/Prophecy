from pathlib import Path
from collections import deque
from datetime import datetime
import re
near=deque(maxlen=35);reports=[]
for line in (Path(__file__).parents[1]/'Logs/GameAnimationSample3.log').open(errors='replace'):
    if 'Slash2 startup NNE parity' in line:
        tick=next((l for l in reversed(near) if 'tick :' in l),None)
        if tick:
            def stamp(s):return datetime.strptime(s[1:24],'%Y.%m.%d-%H.%M.%S:%f')
            try: ms=(stamp(line)-stamp(tick)).total_seconds()*1000
            except ValueError:continue
            reports.append((line[:25],round(ms,1),tick.strip()))
    if line.startswith('['):near.append(line)
for r in reports[-24:]:print(*r)
