const assert=require('node:assert/strict'),F=require('./fkreturn.js'),R=require('./recovery.js');
const names=['root','spine_01','upperarm_r','lowerarm_r','hand_r'],parents=[-1,0,1,2,3],hand=4,I=[0,0,0,1],dt=1e-5;
const local={q:names.map(()=>I),p:[[0,0,0],[0,0,50],[0,20,20],[30,0,0],[25,0,0]]};
const pose=l=>{const f=R.fk(l,parents);return f.q.map((q,j)=>({q,p:f.points[j],s:[1,1,1]}));};
const last=pose(local),beforeLocal=structuredClone(local),velocity=[0,0,1.2];
beforeLocal.p[hand]=R.rotate(R.qexp(R.mul(velocity,-dt)),local.p[hand]);
const previous=pose(beforeLocal),incoming=R.mul(R.sub(last[hand].p,previous[hand].p),1/dt);
let maxLengthError=0,maxVelocityError=0,cases=0;
for(const worldInertia of [false,true])for(const springReturn of [false,true]){
 const ret=F.prepare({names,parents,last,previous,base:last,previousBase:last,dt,profile:{...F.defaults(),worldInertia,springReturn},handInertia:true});
 const legacy={...ret,model:{...ret.model,offsetVelocity:ret.model.offsetVelocity.map((v,j)=>j===hand?[0,0,0]:v),springCache:null}};
 const at=F.sample(ret,last,dt),old=F.sample(legacy,last,dt),outgoing=R.mul(R.sub(at[hand].p,last[hand].p),1/dt);
 const error=R.length(R.sub(outgoing,incoming));maxVelocityError=Math.max(maxVelocityError,error);
 assert(error<.1,'hand-local translation carries incoming velocity');
 assert(R.length(R.sub(old[hand].p,last[hand].p))<1e-10,'old rotation-only hand omitted this velocity');
 for(let t=0;t<=ret.timing.duration;t+=.017){
  const f=F.sample(ret,last,t);
  for(let j=1;j<names.length;j++){
   const length=R.length(R.sub(f[j].p,f[parents[j]].p)),expected=R.length(local.p[j]);
   maxLengthError=Math.max(maxLengthError,Math.abs(length-expected));assert(Math.abs(length-expected)<1e-8,'fixed bone lengths');
   assert.deepEqual(f[j].q,last[j].q,'position inertia does not alter hand rotation');
  }
 }
 assert.deepEqual(F.sample(ret,last,ret.timing.duration),last,'exact return endpoint');cases++;
}
console.log(JSON.stringify({passed:true,cases,maxLengthError,maxVelocityError}));
