const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js');
const manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json'));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));let cases=0,maxAngularError=0;
for(const clip of manifest.clips)for(const v of clip.variants){
 const b=fs.readFileSync(__dirname+'/'+v.file),m=R.prepare(v,b.buffer.slice(b.byteOffset,b.byteOffset+b.length),clip,manifest.names,manifest.parents);
 for(const spineTurn of [0,-179,125,179]){
  const opt={duration:.31,inertia:1,worldInertia:true,spineTurn,inertiaHold:.25,inertiaDecay:.5,returnEasing:.12},end=R.sample(m,m.attackSeconds,opt),dt=1e-7;
  assert.deepEqual(end,R.sample(m,m.attackSeconds,{...opt,worldInertia:false}),'authored mode changed');
  const first=R.sample(m,m.attackSeconds+dt,opt),previous=R.sample(m,m.attackSeconds-1e-6,opt);
  for(let j=0;j<m.names.length;j++)if(m.inertial[j]){
   const actual=R.mul(R.qlog(R.qm(first.q[j],R.qinv(end.q[j]))),1/dt),expected=R.mul(R.qlog(R.qm(end.q[j],R.qinv(previous.q[j]))),1e6),error=R.length(R.sub(actual,expected));
   maxAngularError=Math.max(maxAngularError,error);assert(error<.003,'world angular handoff');
  }
  for(const fraction of [.1,.25,.5,.9,.999999]){
   const t=m.attackSeconds+opt.duration*fraction,p=R.sample(m,t,opt),local=R.localize(p.points,p.q,m.parents),startLocal=R.localize(end.points,end.q,m.parents);
   assert(p.points.flat().every(Number.isFinite));assert(p.axes.flat(2).every(Number.isFinite));
   for(let j=0;j<m.names.length;j++){
    if(!m.upper[j]){assert(R.length(R.sub(p.points[j],end.points[j]))<1e-8);assert(angle(p.q[j],end.q[j])<1e-8);}
    else assert(Math.abs(R.length(local.p[j])-R.length(startLocal.p[j]))<1e-8,'bone length');
   }
   // Changing ancestor inertia must not rotate an active child's world carry.
   const alternate=R.sample(m,t,{...opt,boneInertia:{spine:0,clavicle:0,upperarm:0,lowerarm:1}});
   for(const name of ['lowerarm_l','lowerarm_r']){const j=m.names.indexOf(name);assert(angle(p.q[j],alternate.q[j])<1e-9,'parent inertia rotated world momentum');}
   const plain=R.sample(m,t,{...opt,inertia:0}),plainLocal=R.localize(plain.points,plain.q,m.parents);
   for(const name of ['hand_l','hand_r']){const j=m.names.indexOf(name);assert(angle(local.q[j],plainLocal.q[j])<1e-9,'hand local inertia introduced');assert(R.length(R.sub(local.p[j],plainLocal.p[j]))<1e-9);}
   assert.deepEqual(plain,R.sample(m,t,{...opt,inertia:0,worldInertia:false}),'zero-inertia mode mismatch');
  }
  assert.strictEqual(R.sample(m,m.attackSeconds+opt.duration,opt),m.idlePose,'idle deadline');
  assert.deepEqual(R.sample(m,m.attackSeconds+.1,{...opt,enabled:false}),end,'disabled mode changed');
  cases++;
 }
}
console.log(JSON.stringify({cases,maxAngularError,passed:'world velocity seam, parent-inertia independence, fixed lengths/lower, hands, exact idle, disabled/zero parity'}));
