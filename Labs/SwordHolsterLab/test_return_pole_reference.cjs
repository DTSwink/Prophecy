const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),fixture=require('./data/straight-arm-regression.json');
const m=H.prepare(data,setup,fixture.returnProfile);let peak=0;
for(let tick=m.plan.slideEnd-4;tick<m.plan.slideEnd+12;tick++){
 const a=H.sampleBody(m,tick/60),b=H.sampleBody(m,(tick+1)/60);
 for(const name of ['upperarm_r','lowerarm_r','hand_r']){
  const j=data.names.indexOf(name),k=data.parents[j],local=f=>R.qm(R.qinv(f.pose[k].q),f.pose[j].q);
  peak=Math.max(peak,H.angle(local(a),local(b)));
 }
}
assert(peak<10,`Return inherited an artificial pole spin: ${peak}`);
for(const time of [m.fkReturn.start,m.plan.slideEnd/60]){
 const a=H.sampleBody(m,time-1e-7),b=H.sampleBody(m,time+1e-7);
 for(const j of m.arm){assert(R.length(R.sub(a.pose[j].p,b.pose[j].p))<.001);assert(H.angle(a.pose[j].q,b.pose[j].q)<.01);}
}
console.log({passed:true,peakDegrees:peak});
