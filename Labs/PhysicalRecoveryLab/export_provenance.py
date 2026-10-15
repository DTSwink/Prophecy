"""Unreal commandlet: supplement provenance without replacing a training export."""
import hashlib
import json
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve();out=root/'Saved/Robotics'
original=(out/'rig.json').read_bytes();old=json.loads(original)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Robotics.ExportRig rig-provenance.json')
assert (out/'rig.json').read_bytes()==original, 'Original training export was unexpectedly replaced'
data=json.loads((out/'rig-provenance.json').read_text(encoding='utf-8-sig'))
assert data['success'] and data['schema']==2, data.get('error')
# All old captured fields must agree. New fields are a supplement, not a
# migration of the rig/model against which checkpoints were trained.
def check(a,b,path=''):
    if isinstance(a,dict):
        for key,value in a.items():
            if key not in ('schema','source_files'):check(value,b[key],path+'/'+key)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):check(x,y,path+'/'+str(i))
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        assert abs(a-b)<=max(1.e-8,abs(a)*1.e-10),(path,a,b)
    else:assert a==b,(path,a,b)
check(old,data)
for relative,fingerprint in old['source_files'].items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==fingerprint['sha256'],relative
data['source_files']=old['source_files'];data['supplements_rig_sha256']=hashlib.sha256(original).hexdigest()
(out/'rig-provenance.json').write_text(json.dumps(data,indent=2))
print('Supplemented velocity/gravity/CCD/material provenance; original export and assets unchanged')
