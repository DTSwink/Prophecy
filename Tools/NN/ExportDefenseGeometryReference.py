"""Extract saved FK call fixtures, without running or altering the oracle."""
from pathlib import Path
import json,shutil
import numpy as np

PROJECT=Path(__file__).resolve().parents[2]
SOURCE=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints')
DEST=PROJECT/'Saved/DefenseIntegration/Models'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    for kind,directory in [('parry','parry_unreal_reference_770015'),('dodge','dodge_unreal_reference/reference')]:
        shutil.copyfile(SOURCE/directory/'skeleton.json',DEST/f'{kind}_skeleton.json')
    cases=[]
    with np.load(SOURCE/'parry_unreal_reference_770015/trace.npz') as trace:
        for key in sorted(trace.files):
            if key.endswith('/raw_fk/output/0'):
                prefix=key[:-len('output/0')]
                cases.append({'key':key,'kind':'raw','args':[trace[prefix+f'input/{i}'].reshape(-1).tolist() for i in (2,3,4,5,6)],
                    'expected':[trace[prefix+f'output/{i}'].reshape(-1).tolist() for i in range(4)]})
            if key.endswith('/transported_fk/output/0'):
                prefix=key[:-len('output/0')]
                kwargs={name:trace[prefix+'kwargs/'+name].reshape(-1).tolist() for name in ('frozen_pos','frozen_rot','baseline_upper') if prefix+'kwargs/'+name in trace}
                cases.append({'key':key,'kind':'finish','args':[trace[prefix+f'input/{i}'].reshape(-1).tolist() for i in (2,3,4,5)],
                    'kwargs':kwargs,'expected':[trace[prefix+f'output/{i}'].reshape(-1).tolist() for i in range(2)]})
    assert cases
    (DEST/'geometry_reference.json').write_text(json.dumps(cases)+'\n')
    print(f'Extracted {len(cases)} saved FK calls.')
    inputs=json.loads((SOURCE/'parry_unreal_reference_770015/inputs.json').read_text())
    episode,cache=inputs['episode'],inputs['cache']
    def flat(value):return np.asarray(value,dtype=np.float32).reshape(-1).tolist()
    primers={'lower':[flat(v) for v in cache['lower'][0][:2]],'upper':[flat(v) for v in episode['upper_primers'][0]],
             'roots':[flat(v) for v in cache['roots'][0][:2]],'baseline1':flat(cache['baseline_upper'][0][1])}
    frames=[]
    with np.load(SOURCE/'parry_unreal_reference_770015/trace.npz') as trace:
        for frame in range(2,len(episode['valid'][0])):
            if not episode['valid'][0][frame]:break
            prefix=f'frame/{frame:03d}/'
            frames.append({'frame':frame,'lower':flat(cache['lower'][0][frame]),'baseline':flat(cache['baseline_upper'][0][frame]),
                'root':flat(cache['roots'][0][frame]),'frozen_p':flat(cache['positions'][0][frame]),'frozen_r':flat(cache['rotations'][0][frame]),
                'pelvis':[flat(episode['pelvis'][0][f]) for f in (frame-1,frame)],
                'collider':[flat(episode['collider'][0][f]) for f in (frame-1,frame)],
                'event':float(episode['event'][0][frame][0]),
                'expected_input':flat(trace[prefix+'network/input']),'expected_delta':flat(trace[prefix+'network/output']),
                'expected_p':flat(trace[prefix+'transported_fk/output/0']),'expected_r':flat(trace[prefix+'transported_fk/output/1']),
                'expected_upper':flat(trace[prefix+'held_target_2/output/1'])})
    document={'primers':primers,'target':flat(episode['target_world'][0]),'attack_type':flat(episode['attack_type'][0]),
              'drawn':inputs['defender_drawn'],'frames':frames}
    (DEST/'parry_recurrence_reference.json').write_text(json.dumps(document)+'\n')
    print(f'Extracted {len(frames)} complete parry transitions.')
    dodge=[]
    with np.load(SOURCE/'dodge_unreal_reference/reference/trace.npz') as trace:
        for key in sorted(trace.files):
            if not key.endswith('/upper/output/0'):continue
            prefix=key[:-len('upper/output/0')]
            state={k:flat(trace[prefix+'state_before/'+k]) for k in ('remaining','current_root','current_axes','initial_delta_world','initial_delta_yaw','root_yaw_offset',
                'previous_lower','previous_upper','current_lower','current_upper','previous_root','previous_axes','root_shift_world')}
            fields=('pelvis_horizontal','left_foot','right_foot','pelvis_rotation','root_horizontal','root_yaw','drop','remaining','enabled','requested_distance','drop_requested_distance')
            frame=int(prefix.split('/')[1])
            dodge.append({'key':key,'state':state,'raw':flat(trace[key])[90:],'expected_output':flat(trace[key]),'expected_input':flat(trace[prefix+'upper/input/0']),
                'valid':bool(trace['episode/valid'][0,frame]),
                'lower_models':{kind:{'input':flat(trace[prefix+kind+'/input/0']),'raw':flat(trace[prefix+kind+'/output'])} for kind in ('walk','run')},
                'expected_pins':flat(trace[prefix+'frozen_cleaned/output/1']),
                'context':{'pelvis':[flat(trace['episode/pelvis'][0,f]) for f in (frame-1,frame)],
                    'collider':[flat(trace['episode/collider'][0,f]) for f in (frame-1,frame)],
                    'target':flat(trace['episode/target_world']),'attack_type':flat(trace['episode/attack_type']),
                    'event':float(trace['episode/event'][0,frame,0])},
                'expected_state':{k:flat(trace[prefix+'proposal/state/'+k]) for k in state},
                'baseline':flat(trace[prefix+'frozen_cleaned/output/0']),
                'expected_controls':{k:flat(trace[prefix+'controls/'+k]) for k in fields},
                'expected_lower':flat(trace[prefix+'proposal/lower_output'])[:41],
                'expected_positions':flat(trace[prefix+'proposal/positions']),
                'expected_rotations':flat(trace[prefix+'proposal/rotations']),
                'expected_root':flat(trace[prefix+'proposal/state/current_root'])+flat(trace[prefix+'proposal/state/current_axes'])})
    assert dodge
    (DEST/'dodge_geometry_reference.json').write_text(json.dumps(dodge)+'\n')
    print(f'Extracted {len(dodge)} saved dodge control/leg/root transitions.')
    models=json.loads((SOURCE/'dodge_unreal_reference/reference/networks.json').read_text())
    settings={}
    for name,entry in models['lower_runtime'].items():
        cfg=entry['config'];policy=entry['metadata']['policy'];foot=policy.get('foot_roll_output_projection',{})
        fake=policy.get('fake_gravity',{});assert not fake.get('strength',fake.get('enabled',False))
        assert cfg['predict_residual'] and policy.get('output_reference_root','current')=='current'
        mode=foot.get('pin_mode','')
        if not mode and any(s in foot.get('rule','').lower() for s in ('logit-selected','lowest-logit','pin/project regardless')):mode='legacy_logit_selected'
        if not mode:mode='continuous_sigmoid'
        assert mode in ('legacy_logit_selected','continuous_sigmoid')
        near=foot.get('near_floor_forced_pin',{})
        settings[name]={'pose_delta_scale':cfg['pose_delta_scale']/30,'speed_scale':cfg['max_speed_scale']/30,
            'turn_scale':cfg['max_turn_rate_per_sec_scale']/30,'ground':cfg.get('foot_roll_ground_y',0),
            'side_blend':cfg.get('foot_roll_side_blend_deg',8)*np.pi/180,'full_height':near.get('full_height_m',.015),
            'fade_height':near.get('fade_height_m',.020),'minimum_pin':near.get('minimum_pin_probability',1),
            'steps':foot.get('integration_steps',60),'legacy_pin':mode=='legacy_logit_selected',
            'height_gate':foot.get('height_pin_gate_enabled',False)}
    (DEST/'dodge_lower_settings.json').write_text(json.dumps(settings,indent=2)+'\n')
    print('Lower inference settings',settings)

if __name__=='__main__':main()
