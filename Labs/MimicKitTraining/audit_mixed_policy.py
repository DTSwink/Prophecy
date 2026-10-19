"""CPU-only paired policy audit on recorded states; never touches the live run."""
import os, sys, io, json, zipfile, math, xml.etree.ElementTree as ET
from pathlib import Path
os.environ['OMP_NUM_THREADS']='2'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitMotorAudit/source/MimicKit/mimickit'))
import numpy as np
import torch
from util import torch_util as q
torch.set_num_threads(2);torch.set_num_interop_threads(1)
OUT=ROOT/'Saved/MimicKitEquipment/mixed-collapse-audit'

def forward(s, obs):
    x=((obs-s['_obs_norm._mean'])/s['_obs_norm._std']).clamp(-10,10)
    h=x
    for i in (0,2,4):h=torch.relu(torch.nn.functional.linear(h,s[f'_model._actor_layers.{i}.weight'],s[f'_model._actor_layers.{i}.bias']))
    mean=torch.nn.functional.linear(h,s['_model._action_dist._mean_net.weight'],s['_model._action_dist._mean_net.bias'])
    phase=torch.nn.functional.linear(h,s['_model._phase_out.weight'],s['_model._phase_out.bias'])
    c=x
    for i in (0,2,4):c=torch.relu(torch.nn.functional.linear(c,s[f'_model._critic_layers.{i}.weight'],s[f'_model._critic_layers.{i}.bias']))
    val=torch.nn.functional.linear(c,s['_model._critic_out.weight'],s['_model._critic_out.bias'])[:,0]
    return mean,phase,val

def main():
    z=zipfile.ZipFile(OUT/'models.zip')
    models={it:torch.load(io.BytesIO(z.read(f'{it}/model.pt')),map_location='cpu',weights_only=True) for it in [38799,38899]}
    source=zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/mixed-getup-starts-source.zip')
    manifest=json.loads(source.read('prepared/manifest.json'));entries={e['id']:e for e in manifest['motions']}
    names=manifest['body_names'];xml=ET.fromstring(source.read('assets/uefn/humanoid_uefn.xml'))
    bodies={e.get('name'):e for e in xml.findall('.//body')}
    parents={child.get('name'):parent.get('name') for parent in xml.findall('.//body') for child in parent.findall('body')}
    offsets={n:torch.tensor([float(x) for x in bodies[n].get('quat','1 0 0 0').split()])[[1,2,3,0]] for n in names}
    reports=[];observations=[];labels=[];groups=[]
    with np.load(io.BytesIO(z.read('38799/replay.npz'))) as replay:
        metadata=json.loads(str(replay['metadata']))
        for i,m in enumerate(metadata['replay_rows']):
            suffix='' if i==0 else '_'+str(i)
            pose=torch.from_numpy(replay['pose'+suffix]).float();wv=torch.from_numpy(replay['world_velocities'+suffix]).float()
            pos,rot=pose[:,:,:3],pose[:,:,3:];count=len(pos)
            joint_rot=[];dof_vel=[]
            for j,n in enumerate(names[1:],1):
                p=names.index(parents[n]);base=q.quat_mul(rot[:,p],offsets[n].expand(count,4))
                joint_rot.append(q.quat_mul(q.quat_conjugate(base),rot[:,j]))
                v=q.quat_rotate(q.quat_conjugate(base),wv[:,j,3:6]-wv[:,p,3:6])
                joints=bodies[n].findall('joint')
                if len(joints)==1:
                    axis=torch.tensor([float(x) for x in joints[0].get('axis','0 0 1').split()]);v=(v*axis).sum(-1,keepdim=True)
                dof_vel.append(v)
            jr=torch.stack(joint_rot,1)
            com=torch.tensor([float(x) for x in bodies['pelvis'].find('inertial').get('pos').split()]).expand(count,3)
            root_vel=wv[:,0,:3]+torch.cross(wv[:,0,3:6],q.quat_rotate(rot[:,0],com),dim=-1)
            obs=torch.cat((pos[:,0,2:3],q.quat_to_tan_norm(rot[:,0]),root_vel,wv[:,0,3:6],q.quat_to_tan_norm(jr).flatten(1),torch.cat(dof_vel,-1),(pos[:,[2,5,8,11,14]]-pos[:,:1]).flatten(1)),-1)
            motion=Path(m.get('idle_motion_file',m['motion_file'])).stem;entry=entries[motion]
            command=torch.tensor([entry['gait'],*entry['direction'],float(m['sword_drawn']),*m['arm_enabled']]).expand(count,-1)
            phase=torch.tensor(m['frame_phase']);obs=torch.cat((obs,command,phase[:,:2]),-1)
            with torch.no_grad():
                a,ph,v=forward(models[38799],obs)
                errors=(torch.nn.functional.normalize(ph,dim=-1)-phase[:,2:4]).abs().amax(-1)
                checksum=errors.max().item()
            reports.append(dict(row=i,clip=Path(m['motion_file']).stem,start=m.get('recovery_start_seconds'),phase_prediction_reconstruction_max_error=checksum,
                worst_frame=int(errors.argmax()),after_reset_max_error=float(errors[1:].max()),mean_error=float(errors.mean())))
            # The initial cached Newton FK uses a different velocity path; use
            # only post-step states whose recorded phase output checks our reconstruction.
            assert float(errors[1:].max()) < 1e-3, 'Recorded observation reconstruction did not validate'
            observations.append(obs[1:]);labels.append(phase[1:,4:]);groups.extend([i]*(count-1))
    obs=torch.cat(observations);target=torch.cat(labels);group=torch.tensor(groups)
    before,after=models.values()
    with torch.no_grad():
        ma,pa,va=forward(before,obs);mb,pb,vb=forward(after,obs)
        shift=mb-ma;kl=.5*(shift/.05).square().sum(-1)
        norm_a=pa.norm(dim=-1);norm_b=pb.norm(dim=-1)
    for row in reports:
        mask=group==row['row']
        row.update(action_shift_normalized_rms=float(shift[mask].square().mean().sqrt()),action_shift_rad_s_rms=float((shift[mask]*before['_a_norm._std']).square().mean().sqrt()),mean_kl=float(kl[mask].mean()),phase_raw_norm_before_min=float(norm_a[mask].min()),phase_raw_norm_after_min=float(norm_b[mask].min()),critic_before_mean=float(va[mask].mean()),critic_after_mean=float(vb[mask].mean()))
    normalizers_equal=all(torch.equal(before[k],after[k]) for k in before if '_norm.' in k)
    config_equal={n:z.read('38799/'+n)==z.read('38899/'+n) for n in ['env_config.yaml','agent_config.yaml','engine_config.yaml','velocity_command_bounds.json']}
    report=dict(before=38799,after=38899,states=len(obs),normalizers_equal=normalizers_equal,configs_equal=config_equal,rows=reports)
    (OUT/'paired-policy.json').write_text(json.dumps(report,indent=2))
    torch.save(dict(obs=obs,target=target,groups=group),OUT/'reconstructed-observations.pt')
    print(json.dumps(dict(states=len(obs),normalizers_equal=normalizers_equal,configs_equal=config_equal,
        reconstruction_error=max(r['phase_prediction_reconstruction_max_error'] for r in reports),
        rows=[{k:r[k] for k in ['row','worst_frame','after_reset_max_error','mean_error']} for r in reports])),flush=True)

if __name__=='__main__':main()
