"""Freeze the requested main-training rollback and curriculum for deployment."""
import copy,hashlib,json,zipfile
from pathlib import Path
import yaml
from uefn_package import runtime_files,verify_package
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'

def main():
    cp=json.loads((OUT/'idle18-resume.json').read_text())
    assert hashlib.sha256(Path(cp['local_path']).read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(OUT/'native-getup-source.zip') as old:
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'))
        cfg['idle_row_fraction']=.60
        cfg['target_radius_m']=.27
        cfg['idle_recovery'].update(fraction=.95,target_radius_m=.30,pelvis_linear_velocity_multiplier=2.,
            start_at_frame_zero=True,absolute_target=False,reset_at_getup_end=True,timeout_only=False,sphere_only=True)
        cfg['idle_recovery'].pop('termination_penalty_per_tick',None)
        cfg.pop('adaptive_motion_rows',None)
        motions=yaml.safe_load(old.read('prepared/motions.yaml'))
        lookup={m['id']:m for m in json.loads(old.read('prepared/manifest.json'))['motions']}
        totals={g:sum(m['weight'] for m in motions['motions'] if lookup[Path(m['file']).stem]['gait']==g) for g in (0,1)}
        for m in motions['motions']:
            gait=lookup[Path(m['file']).stem]['gait']
            if gait in totals:m['weight']*=.5/totals[gait]
        replacements={n:p.read_bytes() for n,p in runtime_files(ROOT).items()}
        for name in ('replay.py','dashboard.py','bridge.py','telemetry.py','preflight_main337.py'):
            replacements['pipeline/'+name]=Path(__file__).with_name(name).read_bytes()
        replacements['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        replacements['prepared/motions.yaml']=yaml.safe_dump(motions,sort_keys=False).encode()
        with zipfile.ZipFile(cp['local_path']) as checkpoint:
            agent_config=yaml.safe_load(checkpoint.read('agent_config.yaml'))
        agent_config['critic_optimizer']['grad_clip']=10.
        replacements['prepared/agent_config.yaml']=yaml.safe_dump(agent_config,sort_keys=False).encode()
        destination=OUT/'main337-native-source.zip'
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as new:
            for entry in old.infolist():new.writestr(copy.copy(entry),replacements.pop(entry.filename,old.read(entry.filename)))
            for n,data in replacements.items():new.writestr(n,data)
        with zipfile.ZipFile(destination) as new:
            verify_package(new,ROOT)
            for n in old.namelist():
                if n.startswith(('motions/','assets/')):assert new.read(n)==old.read(n),n
            with zipfile.ZipFile(cp['local_path']) as checkpoint:
                original_agent=yaml.safe_load(checkpoint.read('agent_config.yaml'))
                original_agent['critic_optimizer']['grad_clip']=10.
                assert original_agent==yaml.safe_load(new.read('prepared/agent_config.yaml'))
    receipt=dict(source=str(destination),sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        bytes=destination.stat().st_size,resume_checkpoint=cp,prior_samples=337739776,
        proportions=dict(idle=.6,loco=.4,walk=.5,run=.5,noisy_idle=.95),
        physics='configured native MJ',reward='reciprocal_sum',termination_penalty=False,critic_grad_clip=10.)
    (OUT/'main337-native-source.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))

if __name__=='__main__':main()
