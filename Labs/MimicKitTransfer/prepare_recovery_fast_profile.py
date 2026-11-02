"""Prepare a local continuation package only. Never uploads, starts or stops a pod."""
from pathlib import Path
import hashlib,json,zipfile,yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'

def main():
    original=ROOT/'Saved/MimicKitEquipment/custom-solver-final-pass/source.zip'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='8af2422292951478a6d2e6bfede507843ad14fcbfce6b114d233bc67fe0637b9'
    with zipfile.ZipFile(original) as z:before={n:z.read(n) for n in z.namelist()}
    files=before.copy()
    files['assets/MimicKitTransfer/contact_engine.py']=(ROOT/'Labs/MimicKitTransfer/contact_engine.py').read_bytes()
    files['assets/MimicKitTransfer/bounded_contact_gpu.py']=(ROOT/'Labs/MimicKitTransfer/bounded_contact_gpu.py').read_bytes()
    inventory=files['pipeline/uefn_package.py'].decode().replace('\r\n','\n')
    assert "'block_contact_gpu.py','coupled_contact_gpu.py'" in inventory
    inventory=inventory.replace("'block_contact_gpu.py','coupled_contact_gpu.py'","'block_contact_gpu.py','bounded_contact_gpu.py','coupled_contact_gpu.py'")
    files['pipeline/uefn_package.py']=inventory.encode()
    old=files['pipeline/uefn_engine.py'].decode().replace('\r\n','\n')
    current=(ROOT/'Labs/MimicKitTraining/uefn_engine.py').read_text()
    # Only the new refresh hook and its use at the end of simulation may differ.
    restored=current.replace('    def refresh_body_velocities(self):\n        # Reset writes generalized velocities before the first physics step.\n        # Observations/replay must not read the previous episode\'s body cache.\n        self._body_velocity.update(self._sim_state.raw_state)\n\n','').replace('        self.refresh_body_velocities()','        self._body_velocity.update(self._sim_state.raw_state)')
    assert restored==old,'Unrelated custom-engine changes require review'
    files['pipeline/uefn_engine.py']=current.encode()
    train=files['pipeline/train.py'].decode().replace('\r\n','\n')
    anchor="                                assert new.get('transfer_floor_aware_projection') is True"
    assert train.count(anchor)==1
    train=train.replace(anchor,anchor+"\n                                old['transfer_solver_profile']=new.get('transfer_solver_profile','legacy_100_50_20')\n                                new.setdefault('transfer_solver_profile','legacy_100_50_20')")
    anchor="floor_guard=True,physics_hz=engine_config['sim_freq'],policy_hz=engine_config['control_freq']))"
    assert train.count(anchor)==1
    train=train.replace(anchor,"floor_guard=True,physics_hz=engine_config['sim_freq'],policy_hz=engine_config['control_freq'],solver=env._engine.transfer_profile_report))")
    anchor="                agent._logger._writer.add_scalar('health/'+tag,detail[key],agent._sample_count)"
    assert train.count(anchor)==1
    train=train.replace(anchor,"                if key in detail:\n    "+anchor)
    compile(train,'train.py','exec');files['pipeline/train.py']=train.encode()
    cfg=yaml.safe_load(files['prepared/engine_config.yaml']);cfg['transfer_solver_profile']='bounded_jolt_40_20'
    files['prepared/engine_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    changed=[n for n in files if files[n]!=before.get(n)]
    assert sorted(changed)==sorted(['assets/MimicKitTransfer/contact_engine.py','assets/MimicKitTransfer/bounded_contact_gpu.py','pipeline/uefn_package.py','pipeline/uefn_engine.py','pipeline/train.py','prepared/engine_config.yaml'])
    for name in changed:
        if name.endswith('.py'):compile(files[name],name,'exec')
    package=OUT/'source-bounded40.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None;z.extractall(OUT/'source-bounded40')
    checkpoint=ROOT/'Saved/MimicKitEquipment/preserved-latest/20261022_131128_uefn_getup_pelvismax7_1024/checkpoint_0161960_final.zip'
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()=='0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b'
    result=dict(source=str(package),sha256=hashlib.sha256(package.read_bytes()).hexdigest(),changed_files=changed,checkpoint=str(checkpoint),launched=False,profile=cfg['transfer_solver_profile'])
    (OUT/'prepared-bounded40.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    rejected=OUT/'prepared-fast24.json'
    if rejected.exists():
        old=json.loads(rejected.read_text());old.update(status='rejected',reason='Full batch slower due to coupled fallback; never launch this profile')
        rejected.write_text(json.dumps(old,indent=2))

if __name__=='__main__':main()
