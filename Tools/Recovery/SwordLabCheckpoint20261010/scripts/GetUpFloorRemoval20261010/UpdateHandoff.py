from pathlib import Path
import json
r=json.loads(Path('Tools/Recovery/GetUpFloorRemoval20261010.json').read_text())
p=Path('ProjectJournal.md');s=p.read_text(encoding='utf-8')
s=s.replace('after adding the get-up floor-correction toggle','after removing the get-up floor-correction feature at the user’s request')
a=s.index('- **New node: Set Get Up Floor Correction.**');b=s.index('- **Get Up is wired and saved',a)
s=s[:a]+'''- **Automatic get-up floor correction and its toggle are removed, as requested.** The PHAT support cache, per-sample pose lift, profile flag, runtime API and feature-only test are gone. Original clip-height alignment and explicit Ground Offset remain. Do not reintroduce the feature from old diagnosis/toggle receipts. Six get-up nodes remain. [Current contract](Docs/GetUp.md); [historical experiment](Docs/Journal/GetUp-floor-correction-history-2026-10-10.md).
- **Removal built and passed actual Play through absolute65:** inactive29, Get Up active30, finite poses in Physical mode. The obsolete `K2Node_CallFunction_280` was removed and execution reconnected from Add Force81 directly to Set Arms Anti Jiggle281. Every other node, pin/default and link matched the pre-removal graph, including the user’s new anti-jiggle/limit settings. User edits were saved/backed up before the required restart; final BP compiled/saved healthy, map unchanged, no dirty packages. One editor restart total for the retained native-layout/reflection removal. Build initially waited for graceful shutdown; a helper pointer-type error was fixed, then the final4-action build passed in58.59s. TestNN is open outside Play. Current log/evidence: `Saved/Diagnostics/GetUpFloorRemoval20261010/`; receipt: `Tools/Recovery/GetUpFloorRemoval20261010.json`.
'''+s[b:]
s=s.replace('Seven nodes provide simulated recovery, optional floor correction, restored magnetization','Six nodes provide simulated recovery, restored magnetization')
s=s.replace('| Current launch log | `Saved/Diagnostics/GetUpFloorToggle20261010/editor.log` |','| Current launch log | `Saved/Diagnostics/GetUpFloorRemoval20261010/editor.log` |')
p.write_text(s,encoding='utf-8')
p=Path('Docs/GetUp.md');s=p.read_text(encoding='utf-8')
s+='\nRemoval verification: normal native build succeeded (final editor rebuild58.59s);\nactual Play remained Physical, inactive at absolute29 and active at30 through65,\nwith finite poses. The user-added floor-correction call was removed and its exec\nflow bypassed directly into Set Arms Anti Jiggle. All other nodes, defaults and\nlinks were preserved exactly; Blueprint compiled/saved healthy and map unchanged.\nOne necessary editor restart handled retained native layout and API removal.\nCurrent receipt: `Tools/Recovery/GetUpFloorRemoval20261010.json`; full evidence:\n`Saved/Diagnostics/GetUpFloorRemoval20261010/`.\n'
p.write_text(s,encoding='utf-8')
