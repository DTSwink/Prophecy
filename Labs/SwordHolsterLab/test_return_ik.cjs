const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const H=require('./holster'),F=require('./fkreturn'),R=require('./recovery'),T=require('./retime');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const saved=require('./data/return-ik-regression.json');
const d=(a,b)=>R.length(R.sub(a,b)),copy=x=>structuredClone(x),arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>data.names.indexOf(n)),root=data.names.indexOf('root');
const blend=(a,b,u)=>R.add(a,R.mul(R.sub(b,a),u));
let maximumTargetError=0,maximumLengthError=0,maximumArmStep=0,cases=0,changed=0;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const sheathe of [false,true]){
 const key=sheathe?'sheatheReturn':'drawReturn',body=sheathe?'sheatheBody':'drawBody';
 const o={...saved,...saved[body],noCheat,motion,sheathe,duration:12,[key]:{...saved[key],armIKEnabled:false}};
 const fk=H.prepare(data,setup,o),ik=H.retime(fk,{...fk.o,[key]:{...fk.o[key],armIKEnabled:true,armIKStart:.1,armIKEnd:.35}});
 assert(fk.plan?.arrives!==false);assert(ik.armReturn||ik.fkReturn);assert.equal(ik.completionTick,fk.completionTick);
 const ret=ik.armReturn||ik.fkReturn,release=fk.plan.slideEnd/60;
 for(let n=0;n<ik.frames.length;n++){
  const a=fk.frames[n],b=ik.frames[n],time=n/60;
  if(time<=release+1e-10)assert.deepEqual(b.pose,a.pose,'pre-release unchanged');
  for(let j=0;j<data.names.length;j++)if(!arm.includes(j))assert.deepEqual(b.pose[j],a.pose[j],'only right arm changes: '+data.names[j]);
  assert(H.angle(b.pose[arm[2]].q,a.pose[arm[2]].q)<1e-5,'wrist rotation controls unchanged');
  for(let k=1;k<3;k++){const error=Math.abs(d(b.pose[arm[k]].p,b.pose[arm[k-1]].p)-d(a.pose[arm[k]].p,a.pose[arm[k-1]].p));maximumLengthError=Math.max(maximumLengthError,error);assert(error<1e-8);}
  if(time>release&&!sheathe)assert.deepEqual(b.sword,H.compose(H.scaledGrip(setup,b.scale),b.pose[arm[2]]));
  const elapsed=time-ret.start,w=F.armIKWeight(ret,elapsed);
  if(w>0){
   const base=H.motion(data,motion,time+ik.motionOffset,ik.o.gazeYaw),rp=p=>R.rotate(R.qinv(base[root].q),R.sub(p,base[root].p));
   const eased=t=>{const x=T.time(ret.curve,t,0,ret.timing.duration)/ret.timing.duration;return x+(x*x*x*(10+x*(-15+6*x))-x)*ret.options.returnEasing;};
   const p0=eased(ret.options.armIKStart*ret.timing.duration),progress=(eased(elapsed)-p0)/(1-p0);
   const direct=R.add(base[root].p,R.rotate(base[root].q,blend(ret.armIK.anchor.point,rp(base[arm[2]].p),progress)));
   const goal=blend(a.pose[arm[2]].p,direct,w),shoulder=b.pose[arm[0]].p,l1=d(a.pose[arm[0]].p,a.pose[arm[1]].p),l2=d(a.pose[arm[1]].p,a.pose[arm[2]].p),dist=d(goal,shoulder);
   if(dist>Math.abs(l1-l2)+.001&&dist<l1+l2-.001){const error=d(b.pose[arm[2]].p,goal);maximumTargetError=Math.max(error,maximumTargetError);assert(error<1e-7);}
   if(d(a.pose[arm[2]].p,b.pose[arm[2]].p)>.01)changed++;
   if(n>0)for(const j of arm.slice(0,2)){const step=H.angle(ik.frames[n-1].pose[j].q,b.pose[j].q);maximumArmStep=Math.max(maximumArmStep,step);}
  }
 }
 // Sample in reverse as well: no hidden time history. Blend boundaries continuous.
 for(const f of [.1,.35,.8]){
  const t=ret.start+ret.timing.duration*f,a=H.sampleBody(ik,t),b=H.sampleBody(ik,t+1e-7);
  assert(d(a.pose[arm[2]].p,b.pose[arm[2]].p)<.001);
  H.sampleBody(ik,ret.start);assert.deepEqual(H.sampleBody(ik,t),a);
 }
 const end=H.sampleBody(ik,Math.ceil((ret.start+ret.timing.duration)*60)/60),oldEnd=H.sampleBody(fk,Math.ceil((ret.start+ret.timing.duration)*60)/60);assert(d(end.pose[arm[2]].p,oldEnd.pose[arm[2]].p)<1e-7);
 // Same current tick after a rotated/translated root.
 const elapsed=ret.timing.duration*.6,t=ret.start+elapsed,base=H.motion(data,motion,t),pose=H.sampleBody(fk,t).pose;
 const a=F.applyArmIK(ret,base,elapsed,pose,H.solve),q=R.qexp([.4,-.2,.6]),v=[5,8,-3],turn=ps=>ps.map(p=>({...p,p:R.add(v,R.rotate(q,p.p)),q:R.qm(q,p.q)}));
 const b=F.applyArmIK(ret,turn(base),elapsed,turn(pose),H.solve),expected=turn(a);
 for(const j of arm){assert(d(b[j].p,expected[j].p)<1e-7);assert(H.angle(b[j].q,expected[j].q)<1e-5);}
 cases++;
}
assert(changed>0);assert(maximumArmStep<30,'no elbow side flips in the captured idle/walk regression');assert.deepEqual(F.sanitize({armIKStart:.8,armIKEnd:.3}).armIKEnd,.8);
console.log(JSON.stringify({passed:true,cases,changed,maximumTargetError,maximumLengthError,maximumArmStep}));
