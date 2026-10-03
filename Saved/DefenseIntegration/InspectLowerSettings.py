import json,pathlib
p=pathlib.Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference/networks.json')
d=json.loads(p.read_text())['lower_runtime']
print('runtime',d.keys())
def walk(v,path=''):
    if isinstance(v,dict):
        for k,w in v.items():
            if not isinstance(w,(list,dict)) and any(t in k for t in ('scale','pin_mode','integration_steps','fake_gravity','end_effectors','clamp_end','output_reference','output_prediction','foot_roll','root_feature')):
                print(path+'/'+k,repr(w))
            if isinstance(w,dict):walk(w,path+'/'+k)
walk(d)
