"""Paired frozen-state transfer probes using the installed Jolt DLL; no editor edits."""
from pathlib import Path
import argparse, json, os, subprocess, tempfile
import CompareNative as ref
import numpy as np

ROOT = ref.ROOT
OUT = ROOT/'Saved/Diagnostics/RobotLocomotion20261026/transfer-audit'
OUT.mkdir(exist_ok=True)


class Jolt:
    def __init__(self, state, flags):
        env = dict(os.environ)
        for k in list(env):
            if k.startswith(('TRANSFER_', 'CAND_')):
                del env[k]
        env.update(TRANSFER_RIG_VELOCITY_STEPS='40', TRANSFER_RIG_POSITION_STEPS='8',
                   TRANSFER_TRAINING_CONTACT='1', TRANSFER_FRICTIONLESS_SELF='1',
                   TRANSFER_NATIVE_BALL_LIMITS='1')
        env.update(flags)
        env={k:v for k,v in env.items() if v is not None}
        env['PATH'] = os.environ.get('AUDIT_DLL_DIR',str(ROOT/'Intermediate/JoltMigration/Install/Development/bin'))+os.pathsep+env['PATH']
        with tempfile.NamedTemporaryFile(mode='w',suffix='.txt',dir=OUT,delete=False) as f:
            np.savetxt(f,state,fmt='%.12g')
        self.error = open(OUT/'fixture-stderr.log','a',encoding='utf-8')
        exe = os.environ.get('AUDIT_FIXTURE',str(ref.folder/'jolt-native-profile/fixture.exe'))
        self.process = subprocess.Popen([exe, f.name], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.error, text=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.state = self.read()
        finally:
            Path(f.name).unlink()
        np.testing.assert_allclose(self.state, state, atol=1e-5, rtol=1e-5)

    def read(self):
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('Fixture exited: '+str(self.process.poll()))
        self.receipt = json.loads(line)
        return np.asarray(self.receipt['bodies'])

    def step(self, action):
        self.process.stdin.write('step '+' '.join(map(str,action))+'\n')
        self.process.stdin.flush()
        self.state = self.read()
        return self.state

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('quit\n'); self.process.stdin.flush(); self.process.wait(10)
        self.error.close()


def policy(state, phase, direction, gait=0):
    obs = ref.transfer.observation(state, {'sword_drawn':False,'arm_enabled':[1,1]},phase).numpy()
    obs[0,146] = gait; obs[0,147:149] = direction if gait>=0 else [1,0]
    action, following = ref.policies[1].run(None, {'observations':obs})
    return action[0], following[0]


def trial(state, phase, direction, backend, ticks, flags):
    history, phases, actions = [state], [phase.copy()], []
    sim = Jolt(state,flags) if backend=='jolt' else ref.reset(state)
    try:
        for tick in range(ticks):
            action, phase = policy(state,phase,direction)
            actions.append(action); phases.append(phase.copy())
            if backend=='jolt':
                state = sim.step(action)
            else:
                sim.ctrl[:] = 0; sim.ctrl[ref.velocity_motors] = action
                for _ in range(8): ref.mujoco.mj_step(ref.model,sim)
                ref.mujoco.mj_forward(ref.model,sim); state = ref.read(sim)
            history.append(state)
    finally:
        if backend=='jolt': sim.close()
    history = np.asarray(history)
    result = dict(backend=backend, min_pelvis_cm=float(history[:,0,2].min()*100),
                  travel_cm=float(np.linalg.norm(history[-1,0,:2]-history[0,0,:2])*100),
                  command_travel_cm=float(np.dot(history[-1,0,:2]-history[0,0,:2],direction)*100),
                  first_fall_tick=next((t for t in range(len(history)) if history[t,0,2]<.6),None))
    return result, dict(states=history,phases=phases,actions=actions)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ticks',type=int,default=150)
    parser.add_argument('--label',default='baseline')
    parser.add_argument('--flags',default='{}')
    parser.add_argument('--sweep',action='store_true')
    args=parser.parse_args(); results=[]
    variants={args.label:json.loads(args.flags)}
    if args.sweep:
        os.environ['AUDIT_FIXTURE']=str(ref.folder/'jolt-native-candidates/fixture.exe')
        common={'CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}
        variants={name:common|flags for name,flags in {
            'candidate_baseline':{},'no_drag':{'TRANSFER_NO_DRAG':'1'},
            'native_motor':{'CAND_NATIVE_MOTOR':'1'},
            'native_motor_no_drag':{'CAND_NATIVE_MOTOR':'1','TRANSFER_NO_DRAG':'1'}}.items()}
    for label, flags in variants.items():
      for case in range(2):
        source=np.load(ROOT/f'Saved/Diagnostics/RobotLocomotion20261026/native-case{case}.npz')
        for backend in (('jolt',) if args.sweep else ('mujoco','jolt')):
            result,trajectory=trial(source['states'][420].copy(),source['phases'][420].copy(),
                                    [1,0] if case==0 else [0,1],backend,args.ticks,flags)
            result.update(case=case,label=label);results.append(result)
            np.savez_compressed(OUT/f'{label}-{backend}-{case}.npz',**trajectory)
            print(json.dumps(result),flush=True)
    (OUT/f'{"sweep" if args.sweep else args.label}.json').write_text(json.dumps(results,indent=2),encoding='utf-8')


if __name__=='__main__': main()
