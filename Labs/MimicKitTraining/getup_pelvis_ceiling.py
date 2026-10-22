"""Calibrated, opt-in high-pelvis failure for perturbed recoveries."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path

import torch
import yaml
from getup_success_gates import replace_once

HELPER = '''def getup_pelvis_failure(perturbed_getup, ticks, pelvis_height, ceiling, grace_ticks):
    return perturbed_getup & (ticks > grace_ticks) & (pelvis_height >= ceiling)


'''


def patch(source):
    source = source.replace('\r\n', '\n')
    source = replace_once(source, 'def getup_success_stability(', HELPER+'def getup_success_stability(')
    anchor = "        self._head_id = names.index('head')\n"
    source = replace_once(source, anchor, anchor+'''        self._pelvis_ceiling_id = names.index('pelvis')
        self._pelvis_ceiling = cfg.get('getup_failure_pelvis_height_m')
        if self._pelvis_ceiling is not None and not (math.isfinite(float(self._pelvis_ceiling)) and self._pelvis_ceiling > 0):
            raise ValueError('Pelvis failure height must be finite and positive')
''')
    anchor = '        flags = torch.where(failed, DoneFlags.FAIL.value, flags)\n'
    source = replace_once(source, anchor, '''        if self._pelvis_ceiling is not None:
            failed |= getup_pelvis_failure(self._perturbed_getup, ticks,
                self._engine.get_body_pos(self._get_char_id())[:, self._pelvis_ceiling_id, 2],
                self._pelvis_ceiling, self._perturb_cfg['getup_failure_pelvis_after_tick'])
'''+anchor)
    anchor = '            getup_max_ticks=self._perturb_cfg[\'getup_ticks\'] if getup else None,\n'
    source = replace_once(source, anchor, anchor+'''            getup_failure_pelvis_height_m=self._pelvis_ceiling if getup else None,
            getup_failure_pelvis_after_tick=self._perturb_cfg.get('getup_failure_pelvis_after_tick') if getup else None,
''')
    ast.parse(source)
    return source


def prepare():
    import resume_getup_success as r
    from backup import verified_readback
    out=r.OUT
    calibration=json.loads((out/'getup-pelvis-ceiling-calibration.json').read_text())
    h=calibration['pelvis_height_m']
    scope={};exec(HELPER,{},scope)
    gate=scope['getup_pelvis_failure']
    result=gate(torch.tensor([True,True,True,True,True,False]),
                torch.tensor([0,5,6,30,6,30]),
                torch.tensor([h+.1,h+.1,h,h,h-.001,h+.1],dtype=torch.float64),h,5)
    assert result.tolist()==[False,False,True,True,False,False]
    plan=json.loads((out/'getup-success-prepared.json').read_text())
    (out/'getup-pelvis-ceiling-previous-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py']=patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion'].update(getup_failure_pelvis_height_m=h,getup_failure_pelvis_after_tick=5)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    local=Path(__file__).with_name('perturbed_omni.py');local.write_text(patch(local.read_text()),encoding='utf-8')
    archive=out/'getup-pelvis-ceiling-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    key='mimickit/pipeline_20261014/equipment/getup-pelvis-ceiling/source_'+digest[:12]+'.zip'
    c=r.cloud.s3();c.put_object(Bucket=r.cloud.rp.VOLUME_ID,Key=key,Body=archive.read_bytes())
    verified_readback(c,r.cloud.rp.VOLUME_ID,key,digest)
    plan['source']=dict(local=str(archive),key=key,sha256=digest)
    plan['run_suffix']='uefn_getup_pelvis_ceiling_1024'
    (out/'getup-pelvis-ceiling-prepared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(dict(source=plan['source'],threshold_m=h,after_tick=5,tests='passed')),flush=True)


if __name__=='__main__':prepare()
