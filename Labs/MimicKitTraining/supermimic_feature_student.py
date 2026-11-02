"""Fit a bounded linear correction on frozen policy features using saved CEM data.

Motivated by SuperTrack's last-layer transfer, not a reproduction of its dynamics
learning. No new teacher collection and no tuning on simulator evaluation.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import torch
from torch import nn
import supermimic_race as base
from supermimic_planning_student import install, audit_student_fit


class FeatureStudent(nn.Module):
    def __init__(self, features, width=512, outputs=34):
        super().__init__()
        self.features=copy.deepcopy(features)
        self.features.requires_grad_(False)
        self.register_buffer('mean',torch.zeros(width))
        self.register_buffer('scale',torch.ones(width))
        self.head=nn.Linear(width,outputs)
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)

    def from_features(self,z):
        return self.head((z-self.mean)/self.scale).clamp(-.225,.225)

    def forward(self,x):
        return self.from_features(self.features(x))


@torch.no_grad()
def fit_head(student, data, alphas=(.0001,.001,.01,.1,1.),chunk=4096):
    """Balanced teacher/anchor ridge regression; select only on held-out worlds."""
    features={k:torch.cat([student.features(v) for v in x.split(chunk)]) for k,(x,y) in data.items()}
    train=[features[k] for k in ['teacher_train','anchor_train']]
    mean=sum(x.mean(0) for x in train)/2
    variance=sum(((x-mean).square().mean(0)) for x in train)/2
    student.mean.copy_(mean);student.scale.copy_(variance.sqrt().clamp_min(.05))
    width=mean.numel();device=mean.device;outputs=data['teacher_train'][1].shape[1]
    gram=torch.zeros(width+1,width+1,device=device,dtype=torch.float64)
    rhs=torch.zeros(width+1,outputs,device=device,dtype=torch.float64)
    for key in ['teacher_train','anchor_train']:
        z=features[key];y=data[key][1]
        for xx,yy in zip(z.split(chunk),y.split(chunk)):
            xx=((xx-student.mean)/student.scale).double()
            xx=torch.cat((xx,torch.ones(len(xx),1,device=device,dtype=xx.dtype)),1)
            gram+=xx.T@xx/len(z);rhs+=xx.T@yy.double()/len(z)
    ridge=torch.eye(width+1,device=device,dtype=torch.float64);ridge[-1,-1]=0
    candidates=[];best=float('inf');selected=None
    for alpha in alphas:
        coefficients=torch.linalg.solve(gram+alpha*ridge,rhs)
        assert torch.isfinite(coefficients).all()
        student.head.weight.copy_(coefficients[:-1].T);student.head.bias.copy_(coefficients[-1])
        errors={}
        for key,z in features.items():
            errors[key]=float((student.from_features(z)-data[key][1]).square().mean())
        validation=errors['teacher_valid']+errors['anchor_valid']
        candidates.append(dict(alpha=alpha,validation=validation,errors=errors))
        if validation<best:
            best=validation;selected=alpha;weights={k:v.clone() for k,v in student.head.state_dict().items()}
    student.head.load_state_dict(weights)
    return dict(selected_alpha=selected,candidates=candidates,selected_audit=audit_student_fit(student,data))


def run(root,checkpoint,output,source,arm):
    start=time.perf_counter();root=Path(root).resolve();output=Path(output).resolve();source=Path(source).resolve()
    output.mkdir(exist_ok=True,parents=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    from learning.base_agent import AgentMode
    def emit(marker,**values):print(marker,json.dumps(values),flush=True)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6843);base.seed(849170)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restore(agent,checkpoint)
    if cfg.get('perturbed_motion',{}).get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();assert not agent._need_normalizer_update()
    agent.eval();agent.set_mode(AgentMode.TEST);agent.requires_grad_(False)
    original={k:v.detach().clone() for k,v in agent.state_dict().items()}
    teacher_report=json.loads((source/'student/result.json').read_text())
    control_report=json.loads((source/'ppo/result.json').read_text())
    assert teacher_report['complete'] and control_report['complete']
    assert teacher_report['training_seed']==control_report['training_seed']==849160
    assert teacher_report['original_parameter_max_abs_delta']==0
    # The old ZIP may have different container timestamps. Verify every original
    # state tensor against the saved teacher's unchanged base policy instead.
    teacher_state=torch.load(source/'student/policy_final.pt',map_location='cuda:0',weights_only=False)
    assert all(torch.equal(v,teacher_state[k]) for k,v in original.items()),'Teacher/base mismatch'
    data_path=source/'student/teacher_data.pt'
    assert hashlib.sha256(data_path.read_bytes()).hexdigest()==teacher_report['teacher_data_sha256']
    report=dict(kind='frozen_feature_student_screen',arm=arm,complete=False,
        original_checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
        teacher_data_sha256=teacher_report['teacher_data_sha256'],source_training_seed=849160,
        reused_teacher_collection_seconds=sum(x['seconds'] for x in teacher_report['teacher_batches']),
        reused_source_worker_seconds=teacher_report['total_worker_seconds'],
        source_control_learning_seconds=control_report['learning_seconds_excluding_checks'],
        fitting_recipe='Frozen original512D motor features, equal teacher/zero-anchor least squares, ridge alpha selected only on heldout worlds; bounded.225 motor residual. Phase/critic/normalizer unchanged. No new simulator teacher.',
        limitations='One reused teacher dataset/training seed. Evaluation seeds are not independent training replications. Reused work and new fitting must be charged before any speed claim.')
    emit('FEATURE_ENV_READY',arm=arm,seconds=time.perf_counter()-start)
    fitting=time.perf_counter()
    student=None
    if arm=='features':
        saved=torch.load(data_path,map_location='cuda:0',weights_only=False)
        assert saved['checkpoint_sha256']==teacher_report['checkpoint_sha256']
        assert saved['training_seed']==849160
        student=FeatureStudent(agent._model._actor_layers).to('cuda:0')
        report['fit']=fit_head(student,saved['data'])
        report['head_parameter_delta_l2']=float(sum(p.square().sum() for p in student.head.parameters()).sqrt())
        assert report['head_parameter_delta_l2']>0
        install(agent._model,student);agent._model._planning_student_enabled=True
        report['original_parameter_max_abs_delta']=max(float((v-agent.state_dict()[k]).abs().max()) for k,v in original.items())
        assert report['original_parameter_max_abs_delta']==0
        torch.save(student.state_dict(),output/'feature_student.pt')
    else:
        assert arm=='ppo'
        policy=source/'ppo/policy_final.pt'
        agent.load_state_dict(torch.load(policy,map_location='cuda:0',weights_only=False),strict=True)
        report['policy_file_sha256']=hashlib.sha256(policy.read_bytes()).hexdigest()
        report['policy_parameter_delta_l2']=float(sum((v-original[k]).float().square().sum() for k,v in agent.state_dict().items()).sqrt())
        assert report['policy_parameter_delta_l2']>0
    report['fit_or_load_seconds']=time.perf_counter()-fitting
    emit('FEATURE_FIT',arm=arm,seconds=report['fit_or_load_seconds'],fit=report.get('fit'),delta=report.get('head_parameter_delta_l2'))
    base.write(output/'result.json',report)
    report['evaluations']={};evaluation_start=time.perf_counter()
    for name,seeds in [('existing',[984160,984161]),('fresh',[984170,984171])]:
        report['evaluations'][name]={}
        for mode,noise in [('deterministic',False),('noisy',True)]:
            rows=base.evaluate(env,agent,seeds,max_ticks=300,exploration=noise)
            report['evaluations'][name][mode]=dict(rows=rows)
            count=sum(sum(g==2 for g in r['row_group']) for r in rows)
            failed=sum(sum(g==2 and f for g,f in zip(r['row_group'],r['row_failed'])) for r in rows)
            emit('FEATURE_EVALUATED',arm=arm,cohort=name,mode=mode,failure=100*failed/count)
            base.write(output/'result.json',report)
    report['evaluation_seconds']=time.perf_counter()-evaluation_start
    report['complete']=True;report['total_worker_seconds']=time.perf_counter()-start
    base.write(output/'result.json',report);emit('FEATURE_COMPLETE',arm=arm,seconds=report['total_worker_seconds'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['root','checkpoint','output','source','arm']:p.add_argument('--'+key,required=True)
    run(**vars(p.parse_args()))
