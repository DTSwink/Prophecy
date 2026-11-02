"""Build retained-stream and initialization references for native NNE tests."""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('footik_export',HERE/'export-nn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from directional_nn import generate_command,yaw_command
from surface_nn import Stream
O=m.PROJECT/'Saved/Diagnostics/FootIKPort20261030/NN';O.mkdir(parents=True,exist_ok=True)

def ort_session(path):
 opts=m.ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
 return m.ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])
def initial_native(bank,encoder,step,settings):
 gait=settings['gait'];direction=settings['direction'];phase=settings['phase'];speed=bank['walkSpeed'] if gait=='walk' else bank['directionMeta']['commandSpeed']
 duration=.1 if settings['terrain']=='incline' else settings.get('duration',.2);stride=bank['strideTicks'][gait]/2;start=60+round((phase%1)*stride);count=math.ceil(duration*30)+2;total=start+count
 cur=np.array(bank['roots'][1],np.float32);roots=np.zeros((total+9,3),np.float32);roots[0]=bank['roots'][0]
 for i in range(1,len(roots)):
  roots[i]=cur;roots[i,2]+=np.float32(speed*(i-1)/30)
 yaws=np.array([yaw_command((i-1-start)/30,speed,settings.get('rootYawSpeed',0),settings.get('rootYawStart',0),settings.get('rootYawStop')) for i in range(len(roots))],np.float32)
 def win(k):return dict(roots=roots[k:k+10].tolist(),rootYawDegrees=yaws[k:k+10].tolist())
 encoded=encoder.run(None,{'input':m.pack_seed(bank['seeds'],win(0),True).numpy()})[0];state=encoded[:,:370];origin=encoded[:,370:373]
 points=[];axes=[];height=[];source_origin=roots[start+1].copy();source_origin[1]=0
 for k in range(total-1):
  output=step.run(None,{'input':np.concatenate((state,m.pack_window(win(k)).numpy(),origin),-1)})[0];state=output[:,:370];row=k+1
  if max(0,start-math.ceil(stride))<=row<start:height.append(float(output[0,374])-float(roots[row+1,1]))
  if row<start:continue
  points.append((output[0,373:448].reshape(25,3)-source_origin).tolist());axes.append(output[0,448:673].reshape(25,3,3).tolist())
 return dict(points=points,axes=axes,roots=(roots[start+1:total+1]-source_origin).tolist(),referenceHeight=sum(height)/len(height),duration=duration)

@ m.torch.inference_mode()
def main(directions,full_course=False):
 report=[]
 for direction in directions:
  owner=m.ResumeLocomotion('run');m.configure_direction(owner,'run',direction);owner.runtime.install_policy();stem='run-'+direction
  bank=json.loads((m.OUT/(stem+'-seed.json')).read_text());encoder=ort_session(m.OUT/(stem+'-seed.onnx'));step=ort_session(m.OUT/(stem+'-step.onnx'))
  # Saved phase changes only visible starting pose, never the command speed.
  for gait,phase,yaw in [('walk',.91,120),('run',.37,-90)]:
   settings=dict(gait=gait,direction=direction,terrain='stairs' if full_course else 'incline',phase=phase,rootYawSpeed=yaw,rootYawStart=0,rootYawStop=10,duration=5 if full_course else .1,totalDuration=5)
   expected=generate_command(owner,dict(settings,policy='run',seedOnly=True));actual=initial_native(bank,encoder,step,settings)
   errors={k:float(np.max(np.abs(np.array(actual[k])-np.array([p[k] for p in expected['poses']])))) for k in ('points','axes')}
   errors['roots']=float(np.max(np.abs(np.array(actual['roots'])-np.array(expected['roots']))));errors['referenceHeight']=abs(actual['referenceHeight']-expected['directionMeta']['referenceHeight'])
   assert max(errors.values())<.0003,(direction,gait,errors)
   name=direction+'-'+gait+('-full' if full_course else '');fixture=dict(kind='initialize',settings=settings,expected=expected,tolerance=.0003);(O/(name+'-initial.json')).write_text(json.dumps(fixture,separators=(',',':')))
   report.append(dict(name=name,kind='initialize',errors=errors));print(report[-1],flush=True)
  if full_course:continue
  # Stops, reversal, changing future heading and explicit reset from30Hzhistory.
  seed=m.command_seed(owner);names=['root',*seed['names']];full=bank['seeds'];stream=Stream(owner);roots=[seed['roots'][0],seed['roots'][1]];base=np.array(roots[-1],np.float32)
  for i in range(1,44):
   velocity=2 if i<10 else 0 if i<16 else -1.5 if i<24 else 3
   base=base+np.array([0,0,velocity/30],np.float32);roots.append(base.tolist())
  yaws=[120*max(0,min(i-5,24))/30 for i in range(len(roots))];records=[];prior=[]
  for i in range(26):
   request=dict(gait='walk',policy='run',direction=direction,names=names,drawn=False,frames=2,roots=roots[i:i+12],rootYawDegrees=yaws[i:i+12])
   if i==0:request['seeds']=full
   if i==15:
    request['reset']=True;request['seeds']=prior[-2:]
   response=stream.step(request);prior.append(response['pose']);records.append(dict(request=request,expected=response))
  (O/(direction+'-stream.json')).write_text(json.dumps(dict(kind='stream',settings=dict(direction=direction,gait='walk'),steps=records,tolerance=.0003),separators=(',',':')))
  report.append(dict(name=direction,kind='stream',steps=len(records),resetAt=15));print(report[-1],flush=True)
 summary=O/'python-reference-summary.json'
 old=json.loads(summary.read_text()) if summary.exists() else []
 keys={(r['name'],r['kind']) for r in report};report=[r for r in old if (r['name'],r['kind']) not in keys]+report
 summary.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--direction',action='append');p.add_argument('--full-course',action='store_true');a=p.parse_args();main(a.direction or ['forward','backward','left','right'],a.full_course)
