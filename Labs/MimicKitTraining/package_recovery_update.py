"""Replace only the two reauthored recovery clips and their existing reset IK."""
import copy,hashlib,json,pickle,zipfile
from pathlib import Path
import numpy as np
from uefn_package import verify_package

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
STAGE=OUT/'recovery-update-20261018'

def main():
    imports=json.loads((STAGE/'imports.json').read_text())
    for item in imports:
        assert hashlib.sha256(Path(item['original_source']).read_bytes()).hexdigest()==item['source_fbx_sha256'], 'Source changed during preparation'
    replacements={}; report=[]
    with zipfile.ZipFile(OUT/'main337-native-source.zip') as old:
        verify_package(old,ROOT)
        for stem in ('getUp_front_quick','getUp_back_quick'):
            variants={}
            for suffix in ('robotic','reset_hand_ik','reset_floor_ik'):
                name=stem+'_'+suffix+'.pkl';data=(STAGE/name).read_bytes()
                clip=pickle.loads(data);f=np.asarray(clip['frames'])
                assert f.ndim==2 and f.shape[1]==40 and len(f)>2 and np.isfinite(f).all()
                assert clip['fps']==30 and clip['loop_mode']==0
                variants[suffix]=clip
                replacements['motions/recovery/'+name]=data
            target=variants['robotic']['frames']
            for clip in variants.values():
                assert clip['frames'].shape==target.shape
                np.testing.assert_array_equal(clip['frames'][:,:6],target[:,:6])
            previous=pickle.loads(old.read('motions/recovery/'+stem+'_robotic.pkl'))
            report.append(dict(motion=stem,old_frames=len(previous['frames']),new_frames=len(target),
                seconds=(len(target)-1)/30,first_frame_max_coordinate_change=float(np.abs(target[0]-previous['frames'][0]).max()),
                target_sha256=hashlib.sha256(replacements['motions/recovery/'+stem+'_robotic.pkl']).hexdigest()))
        for source,target in [('report.json','recovery_retarget_report.json'),('imports.json','recovery_imports.json'),
                              ('hand-ik-report.json','recovery_hand_ik_report.json'),('foot-reset-ik-report.json','recovery_foot_reset_ik_report.json')]:
            replacements['docs/'+target]=(STAGE/source).read_bytes()
        for name in ('prepare_recovery_starts.py','prepare_recovery_hand_ik.py','prepare_recovery_foot_resets.py'):
            replacements['pipeline/'+name]=Path(__file__).with_name(name).read_bytes()
        dest=OUT/'updated-recovery-source.zip'
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as new:
            for entry in old.infolist():new.writestr(copy.copy(entry),replacements.get(entry.filename,old.read(entry.filename)))
            for name,data in replacements.items():
                if name not in old.namelist():new.writestr(name,data)
        with zipfile.ZipFile(dest) as new:
            verify_package(new,ROOT)
            changed=[name for name in old.namelist() if old.read(name)!=new.read(name)]
            assert all(name in replacements for name in changed)
            assert not any(name.startswith(('prepared/','assets/')) for name in changed)
    receipt=dict(source=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size,
        clips=report,changed=changed,source_imports=imports,method='Unchanged anchor projection; same separate hand and foot reset IK; no abandoned cleanup or pelvis shifts')
    (OUT/'updated-recovery-source.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k!='source_imports'},indent=2))

if __name__=='__main__':main()
