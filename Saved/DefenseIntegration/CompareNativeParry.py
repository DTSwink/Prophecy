from pathlib import Path
import sys,json
base=Path(__file__).resolve().parent
sys.path.insert(0,str(base/'ReferenceSources/parry/training/slashes2/ParryAndDodge'))
from compare_ue5_parry_reference import read,compare
reference=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/parry_unreal_reference_770015/parity_expected.json')
candidate=base/'Models/ue_parry_candidate.json'
report=compare(read(reference),read(candidate))
(base/'Models/unreal_parry_full_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
