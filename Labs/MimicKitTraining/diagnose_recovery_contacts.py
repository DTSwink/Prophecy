"""Small local first-failure capture, no policy update or cloud job."""
import os,sys,json,zipfile,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import torch,warp as wp,yaml,numpy as np,mujoco
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util
out=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
torch.set_num_threads(1);torch.manual_seed(173);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6792)
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
cfg,ec,ac=[yaml.safe_load((out/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
cfg['idle_row_fraction']=.99
env=RecoveryOmniEnv(cfg,ec,64,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
with zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/recovery-fallback-checkpoint.zip') as z:
    agent.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True))
agent.eval();agent.set_mode(AgentMode.TRAIN)
obs,info=env.reset()
for tick in range(64):
    prior=dict(start=env._recovery_start.cpu().tolist(),motion=env._recovery_motion.cpu().tolist(),time=env._time_buf.cpu().tolist())
    with torch.no_grad():action,_=agent._decide_action(obs,info);obs,r,done,info=env.step(action)
    capture=env._engine.failure_capture
    if int(capture.seen.numpy()[0]):
        path=out/'first-contact-failure.npz';capture.save(path)
        data=np.load(path);world=int(data['original_world']);model=env._engine._solver.mj_model
        d=mujoco.MjData(model);d.qpos[:]=data['qpos'][0];d.qvel[:]=data['qvel'][0];mujoco.mj_forward(model,d)
        contacts=[dict(shapes=[model.geom(int(g)).name for g in c.geom],depth_m=float(c.dist),position=c.pos.tolist()) for c in d.contact]
        report=dict(world=world,tick=tick+1,motion=prior['motion'][world],start=prior['start'][world],time=prior['time'][world],
            captured_sizes=data['manifold_size'][0,:int(data['manifold_count'][0])].tolist(),contacts_at_captured_pose_cpu=contacts,
            finite=all(np.isfinite(data[k]).all() for k in ('qpos','qvel','velocity','motor_impulse')))
        (out/'first-contact-failure.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);break
    obs,info=env.reset(torch.nonzero(done,as_tuple=False).flatten())
else:raise RuntimeError('No failure reproduced in bounded diagnostic')
