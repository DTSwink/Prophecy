import numpy as np,json,pathlib,re,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
def unit(v):return np.array(v)/np.linalg.norm(v)
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def rotate(v,a,t):return v*np.cos(t)+np.cross(a,v)*np.sin(t)+a*np.dot(a,v)*(1-np.cos(t))
def solve(oldaxis,oldpole,axis,d):
 pole=unit(oldpole-(oldaxis+axis)*np.dot(oldpole,axis)/(1+np.dot(oldaxis,axis)))
 along=(.45**2-.43**2+d*d)/(2*d);radius=np.sqrt(.45**2-along*along)
 sa=axis[1];n0=np.array([0,1,0])-axis*sa;nl=np.linalg.norm(n0);n=unit(n0);q=-along*sa/(radius*nl)
 strength=smooth(nl*nl*4)*smooth((1-abs(q))*4)
 desired=n*np.clip(q,-1,1)+unit(np.cross(axis,n))*np.sqrt(max(0,1-np.clip(q,-1,1)**2))
 turn=np.arctan2(np.dot(axis,np.cross(pole,desired)),np.dot(pole,desired))*strength
 pole=rotate(pole,axis,turn)
 return axis*along+pole*radius,pole,{'q':q,'strength':strength,'turn_deg':float(np.degrees(turn)),'plane_error_cm':float((axis*along+pole*radius)[1]*100)}
axis=np.array([0,np.sqrt(.6),-np.sqrt(.4)])
upper,pole,ob=solve(axis,np.array([-1,0,0]),axis,.35)
ob.update(pole_forward_dot=float(pole[0]),upper=upper.tolist())
oldaxis=np.array([0,0,-1]);oldpole=np.array([1,0,0]);oldUpper=None;out=[]
for i in range(121):
 a=1+i/120;axis=np.array([0,np.sin(a),-np.cos(a)])
 upper,pole,rec=solve(oldaxis,oldpole,axis,.35)
 step=0 if oldUpper is None else np.arccos(np.clip(np.dot(unit(upper),unit(oldUpper)),-1,1))
 rec.update(index=i,angle=a,step_radians=float(step),step_degrees=float(np.degrees(step)),upper=upper.tolist())
 out.append(rec);oldaxis=axis;oldpole=pole;oldUpper=upper
worst=max(out,key=lambda x:x['step_radians'])
def body(path):
 s=path.read_text();s=s[s.index('void ResolveTemperedLeg'):];s=s[s.index('{'):s.index('\n#if WITH_DEV_AUTOMATION_TESTS')]
 return s
old=body(root/'Saved/Diagnostics/SupportSourceExperiments/ProphecyLowerTempering-experiments.inl');new=body(root/'Source/GameAnimationSample3/Private/ProphecyLowerTempering.inl')
def normalize(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*','',s))
def prefix(s):
 idx=s.index('auto Solve=');end=s.index('};',idx)+2
 return s[:end]
def suffix(s):return s[s.index('if (S.FeetRotation==0.f) return;'):]
oldsuf=suffix(old).replace('* ((ExperimentMode==1 || ExperimentMode==2) ? 1.f-Support : 1.f)','')
oldnormalized=normalize(prefix(old)+'Solve(Previous,Target);'+oldsuf)
newnormalized=normalize(prefix(new)+'Solve(Previous,Target);'+suffix(new))
same=oldnormalized==newnormalized
data={'oblique':ob,'sideways_worst':worst,'sideways_neighbors':out[max(0,worst['index']-2):worst['index']+3],
 'old_mode0_vs_final_null_source_normalized_equal':same,'simplifications':'Mode0 source branch -> Solve(Previous,Target), strength multiplier ->1; null NNSource -> Solve(Previous,Target); comments/whitespace stripped.',
 'old_sha256':hashlib.sha256(oldnormalized.encode()).hexdigest(),'new_sha256':hashlib.sha256(newnormalized.encode()).hexdigest()}
refinement=[]
for steps in [120,240,480,960]:
 axis=np.array([0,np.sin(1),-np.cos(1)]);pole=np.array([1.,0,0])
 for _ in range(32):upper,pole,_=solve(axis,pole,axis,.35)
 peak=0;where=0
 for i in range(1,steps+1):
  a=1+i/steps;na=np.array([0,np.sin(a),-np.cos(a)])
  nu,npole,_=solve(axis,pole,na,.35);diff=np.arccos(np.clip(np.dot(unit(upper),unit(nu)),-1,1))
  if diff>peak:peak=diff;where=i
  axis,pole,upper=na,npole,nu
 refinement.append({'subdivisions':steps,'worst_radians':float(peak),'worst_degrees':float(np.degrees(peak)),'index':where})
data['settled_sweep_refinement']=refinement
(root/'Saved/Diagnostics/RecoveryCandidateReviewLegacyTests.json').write_text(json.dumps(data,indent=2))
print(json.dumps(data,indent=2))
