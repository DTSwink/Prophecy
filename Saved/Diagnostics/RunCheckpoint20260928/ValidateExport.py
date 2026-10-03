import sys,json,pathlib,hashlib
import numpy as np
import torch
from onnx.reference import ReferenceEvaluator
p=pathlib.Path(__file__).resolve().parent
root=p.parents[2]
old=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
new=json.loads((p/'export/prophecy_lower_body_runtime.json').read_text())
changes={k:dict(old=old.get(k),new=new.get(k)) for k in new if old.get(k)!=new.get(k) and k not in ('checkpoint_path','checkpoint_sha256','onnx_path','onnx_sha256','seed_phase_states','seed_prev_state','seed_cur_state')}
(p/'contract_changes.json').write_text(json.dumps(changes,indent=2))
print('CHANGED_CONTRACT_FIELDS',list(changes))
for k in ('batch_size','input_dim','model_output_dim','runtime_output_dim','state_dim','future_window','max_speed_scale_final','max_turn_rate_scale_final','pose_delta_scale_final','output_reference_root','output_prediction_mode','body_mode','body_names','parents_body','local_offsets_m','seed_root_rotation_rows'):
    assert old.get(k)==new.get(k),(k,old.get(k),new.get(k))
sys.path.insert(0,r'C:/Users/singerie/Documents/Cursor/stepper')
from training.ik import ik_core as tl,train_simple_ae_controller as ctl,visualize
cp=torch.load(p/'source_checkpoint.pt',map_location='cpu',weights_only=False)
print('CHECKPOINT_PROGRESS',{k:v for k,v in cp.items() if k in ('step','global_step','epoch','iteration','train_step')})
visualize.apply_simple_controller_policy(cp)
cfg=tl.TrainConfig();visualize.apply_config_dict(cfg,cp['config']);cfg.device='cpu';cfg.cyclic_animation=True
clip=tl.MotionClip(pathlib.Path(new['seed_clip_path']),cfg,cyclic_animation=True)
store=ctl.SimpleClipStore([clip],cfg,torch.device('cpu'))
model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
ids=torch.zeros(100,dtype=torch.long);prev=torch.zeros_like(ids);cur=torch.ones_like(ids)
pv,pp,pl=ctl.target_state(store,ids,prev);cv,cc,cl=ctl.target_state(store,ids,cur)
x=ctl.build_controller_input(store,ids,cur,pv,cv,pp,cc,pl,cl)
session=ReferenceEvaluator(str(p/'export/prophecy_lower_body_run_b100.onnx'))
results=[]
torch.manual_seed(123)
for noise in (0.,.001,.01):
    inp=x+torch.randn_like(x)*noise
    with torch.no_grad():expected=model(inp).numpy()
    actual=session.run(None,{session.input_names[0]:inp.numpy()})[0]
    assert actual.shape==(100,43) and np.isfinite(actual).all()
    np.testing.assert_allclose(actual,expected,rtol=1e-4,atol=1e-5)
    results.append(dict(noise=noise,max_abs_error=float(np.max(np.abs(actual-expected)))))
report=dict(checkpoint_progress={k:v for k,v in cp.items() if k in ('step','global_step','epoch','iteration','train_step')},parity=results,contract_changes=list(changes))
(p/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
