"""Same eight recorded substep inputs, changing only native contact settings."""
import os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
os.environ['MIMICKIT_TRANSFER_OUT']=str(OUT)
os.environ['MIMICKIT_TRANSFER_FIXTURE']=str(OUT/'ablation-saturation.exe')
os.environ['TRANSFER_SUBSTEPS']='1'
from native_probe import Native,np,R

data=json.loads((OUT/'contact-substeps.json').read_text())
commands=json.loads((OUT/'baseline-motor-inputs.json').read_text())['commands']
reports=[]
for name,settings in [('default',()),('training_material',('TRANSFER_TRAINING_CONTACT',)),
                      ('no_speculative',('TRANSFER_NO_SPECULATIVE',)),
                      ('training_material_no_speculative',('TRANSFER_TRAINING_CONTACT','TRANSFER_NO_SPECULATIVE'))]:
    for flag in ('TRANSFER_TRAINING_CONTACT','TRANSFER_NO_SPECULATIVE'):os.environ.pop(flag,None)
    for flag in settings:os.environ[flag]='1'
    rows=[]
    for initial,output in zip(data['inputs'],data['outputs']):
        n=Native(initial)
        try:result=n.request('step '+' '.join(map(str,commands)))
        finally:n.close()
        native=np.array(result['bodies']);actual=np.array(output['actual'])
        angle=(R.from_quat(native[:,3:7])*R.from_quat(actual[:,3:7]).inv()).magnitude()
        rows.append(dict(angle_deg=float(np.rad2deg(angle.max())),position_cm=float(np.linalg.norm(native[:,:3]-actual[:,:3],axis=1).max()*100),
                         impulse_ns=float(sum(result['ground_vertical_impulse_ns']))))
    reports.append(dict(case=name,steps=rows));print(json.dumps(reports[-1]),flush=True)
(OUT/'contact-settings-comparison.json').write_text(json.dumps(reports,indent=2))
