"""Frozen native checkpoint: causal single-step and whole-episode Jolt comparisons."""
from getup_transfer import *
DEST=OUT/'jolt-native-candidates'
os.environ['GETUP_JOLT_FIXTURE']=str(DEST/'fixture.exe')
BASE=dict(TRANSFER_RIG_VELOCITY_STEPS='40',TRANSFER_RIG_POSITION_STEPS='8',
          TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1')
CASES={
 'baseline':{},
 'native_drag':dict(TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1'),
 'explicit':dict(CAND_EXPLICIT='1'),
 'explicit_native_drag':dict(CAND_EXPLICIT='1',TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1'),
 'gain_half':dict(CAND_GAIN='.5'),
 'gain_double':dict(CAND_GAIN='2'),
 'zero_slop':dict(CAND_SLOP='0',TRANSFER_NO_SPECULATIVE='1'),
 'low_projection':dict(CAND_BAUMGARTE='.02'),
 'no_reduction':dict(CAND_NO_REDUCTION='1'),
 'native_motor':dict(CAND_NATIVE_MOTOR='1',TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1'),
 'native_motor_low':dict(CAND_NATIVE_MOTOR='1',TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1',CAND_BAUMGARTE='.02'),
 'native_motor_nolimit':dict(CAND_NATIVE_MOTOR='1',TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1',TRANSFER_NO_LIMITS='1'),
 'native_motor_nolimit_low':dict(CAND_NATIVE_MOTOR='1',TRANSFER_NO_DRAG='1',CAND_NO_DAMPING='1',CAND_GYRO='1',TRANSFER_NO_LIMITS='1',CAND_BAUMGARTE='.02'),
 'nolimit_low':dict(TRANSFER_NO_LIMITS='1',CAND_BAUMGARTE='.02'),
}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--cases',default=','.join(CASES));a=parser.parse_args()
 pol=Policy('native');results=[]
 for label in a.cases.split(','):
  for key in list(os.environ):
   if key.startswith(('TRANSFER_','CAND_')):del os.environ[key]
  os.environ.update(BASE|CASES[label]);report=dict(candidate=label,settings=BASE|CASES[label],rows=[])
  for index in [3,8,9,16]:
   row,states=replay('native',index);phase=np.array(row['frame_phase'][0][:2]);sim=Jolt(states[0]);current=np.array(sim.initial['bodies']);history=[current];actions=[]
   for tick in range(1,181):
    act,pred=pol(observation(current,row,phase));phase=pred[0];current=np.array(sim.request('step '+' '.join(map(str,act[0])))['bodies']);history.append(current);actions.append(act[0])
    if tick==1:err=dict(position=float(np.max(np.linalg.norm(current[:,:3]-states[1,:,:3],axis=-1))),velocity=float(np.sqrt(np.mean((current[:,7:]-states[1,:,7:])**2))))
    result=outcome(current,tick,row)
    if result:break
   sim.close();entry=dict(row=index,terminal=result,ticks=tick,first_tick_error=err,head=float(current[2,2]),max_head=float(np.max(np.array(history)[:,2,2])))
   report['rows'].append(entry)
   np.savez_compressed(DEST/f'{label}-row{index}.npz',states=history,actions=actions)
  results.append(report);(DEST/('candidates-'+a.cases.split(',')[0]+'.json')).write_text(json.dumps(results,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
