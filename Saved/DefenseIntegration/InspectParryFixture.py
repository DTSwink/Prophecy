import json,pathlib
folder=pathlib.Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/parry_unreal_reference_770015')
def shapes(v):
    if isinstance(v,dict):return {k:shapes(w) for k,w in v.items()}
    if isinstance(v,list):return [len(v),shapes(v[0]) if v else None]
    return type(v).__name__
for name in ('inputs.json','parity_expected.json','parity_dump_schema.json','rollout.json'):
    print(name,shapes(json.loads((folder/name).read_text())))
