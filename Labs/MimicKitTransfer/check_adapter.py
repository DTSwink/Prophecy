"""Physical action-bound and saved-policy regression checks, no training."""
from native_probe import *

def main():
    data=np.load(OUT/'newton_phase_0.250.npz');initial=data['physical'][1]
    errors=[]
    for sign in (-1,1):
        states=[]
        for magnitude in (100.,float(np.float32(2*np.pi))):
            p=Native(initial)
            try:states.append(np.array(p.request('step '+' '.join([str(sign*magnitude)]*34))['bodies']))
            finally:p.close()
        errors.append(float(np.max(np.abs(states[0]-states[1]))))
    assert max(errors)<1e-7,errors
    report=dict(passed=True,positive_negative_bound_state_difference=errors,
                motor_self_test=json.loads((OUT/'motor-test.json').read_text()),
                note='Actor replay equivalence and all151 observation channels checked by native_probe.py')
    (OUT/'adapter-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
