import json,pathlib
root=pathlib.Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints')
for folder in [root/'parry_unreal_reference_770015',root/'dodge_unreal_reference/reference']:
    d=json.loads((folder/'skeleton.json').read_text())
    print(folder.name,'names',d['joint_names'],'parents',d['parents'])
    print('geometry',[(k,list(v) if isinstance(v,dict) else type(v).__name__) for k,v in d['geometry'].items()])
    for k in ['core_bones','arm_specs','lower_limb_specs','lower_payload_slices']:print(k,d[k])
