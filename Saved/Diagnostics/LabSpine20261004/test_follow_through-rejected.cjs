const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js');
const manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json')),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let cases=0,worstFineStep=0;
for(const clip of manifest.clips)for(const v of clip.variants){
 const bytes=fs.readFileSync(__dirname+'/'+v.file),m=R.prepare(v,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents);
 for(const worldInertia of [false,true])for(const inertiaHold of [0,.25,.8]){
  const o={duration:.31,inertia:1,followThrough:true,worldInertia,inertiaHold,inertiaDecay:.5,returnEasing:.12,spineTurn:125},tail=m.attackSeconds,dt=1e-7,end=R.sample(m,tail,o),before=R.sample(m,tail-1e-6,o),first=R.sample(m,tail+dt,o);
  for(let j=0;j<m.names.length;j++)if(m.inertial[j]){const a=R.mul(R.qlog(R.qm(first.q[j],R.qinv(end.q[j]))),1/dt),b=R.mul(R.qlog(R.qm(end.q[j],R.qinv(before.q[j]))),1e6);assert(R.length(R.sub(a,b))<.01,'outgoing angular velocity');}
  for(const f of [.01,.25,.5,.8,.99,.999999]){
   const pose=R.sample(m,tail+f*o.duration,o),l=R.localize(pose.points,pose.q,m.parents),idle=R.sample(m,tail+f*o.duration,{...o,inertia:0}),il=R.localize(idle.points,idle.q,m.parents);
   assert(pose.points.flat().every(Number.isFinite));assert(pose.axes.flat(2).every(Number.isFinite));
   for(let j=0;j<m.names.length;j++){
    if(!m.upper[j]){assert(R.length(R.sub(pose.points[j],end.points[j]))<1e-8);assert(angle(pose.q[j],end.q[j])<1e-8);}
    else assert(Math.abs(R.length(l.p[j])-R.length(m.locals.at(-1).p[j]))<1e-8,'bone length');
   }
   for(const name of ['hand_l','hand_r']){const j=m.names.indexOf(name);assert(angle(l.q[j],il.q[j])<1e-8,'hand local inertia');assert(R.length(R.sub(l.p[j],il.p[j]))<1e-8);}
  }
  if(inertiaHold>0){const t=tail+inertiaHold*o.duration,a=R.sample(m,t-dt,o),b=R.sample(m,t,o),c=R.sample(m,t+dt,o);for(let j=0;j<m.names.length;j++)if(m.inertial[j]){const va=R.mul(R.qlog(R.qm(b.q[j],R.qinv(a.q[j]))),1/dt),vb=R.mul(R.qlog(R.qm(c.q[j],R.qinv(b.q[j]))),1/dt);assert(R.length(R.sub(va,vb))<.05,'hold-release jump');}}
  assert.strictEqual(R.sample(m,tail+o.duration,o),m.idlePose);assert.deepEqual(R.sample(m,tail+.15,{...o,inertia:0}),R.sample(m,tail+.15,{...o,inertia:0,followThrough:false}));cases++;
 }
 // Sweep the most aggressive hold to catch moving shortest-arc branch flips.
 const o={duration:.31,inertia:1,followThrough:true,worldInertia:true,inertiaHold:.8,inertiaDecay:.5,returnEasing:0};let prev=R.sample(m,m.attackSeconds,o);
 for(let k=1;k<=155;k++){const pose=R.sample(m,m.attackSeconds+k*.002,o);for(let j=0;j<m.names.length;j++)worstFineStep=Math.max(worstFineStep,angle(pose.q[j],prev.q[j])*180/Math.PI);prev=pose;}
}
assert(worstFineStep<30,'abrupt rotation branch change');
console.log(JSON.stringify({cases,worstFineStep,passed:'angular entry, hold seam, finite FK, lengths/lower/hands, idle deadline, zero parity and fine rotation sweep'}));
