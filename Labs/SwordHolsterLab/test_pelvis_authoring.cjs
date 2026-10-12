const assert=require('node:assert/strict'),fs=require('node:fs'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const changed=structuredClone(data),indices=['spine_01','spine_02','spine_03','spine_04','spine_05','clavicle_r','upperarm_r','lowerarm_r','hand_r'].map(n=>data.names.indexOf(n));
// Adversarial ongoing gait: independently turn every driven joint after entry.
changed.motions.run.frames=changed.motions.run.frames.map((frame,i)=>{
 if(i<=71)return frame;
 const local=R.localize(frame.map(v=>v.slice(0,3)),frame.map(v=>v.slice(3)),data.parents);
 for(const [k,j] of indices.entries())local.q[j]=R.qm(R.qexp([Math.sin(i*.2+k)*.7,Math.cos(i*.14+k)*.3,.2]),local.q[j]);
 const out=R.fk(local,data.parents);return out.points.map((p,j)=>[...p,...out.q[j]]);
});
let maxDifference=0,maxLeftAngleError=0;
for(const sheathe of [true,false]){
 const action=sheathe?'sheathe':'draw',o={...saved,motion:'run',sheathe,startTick:70,[action+'Return']:{enabled:false},duration:10};
 const a=H.prepare(data,setup,o),b=H.prepare(changed,setup,o);assert.equal(a.plan.endTick,b.plan.endTick,'future gait cannot change planned arrival');assert.equal(a.plan.slideEnd,b.plan.slideEnd);
 for(let tick=70;tick<=a.plan.slideEnd;tick+=.27){
  const p=H.sampleBody(a,tick/60).pose,q=H.sampleBody(b,tick/60).pose;
  for(const j of indices){const error=R.length(R.sub(p[j].p,q[j].p));maxDifference=Math.max(maxDifference,error);assert(error<1e-7,'authored position independent of future driven gait');assert(R.length(R.qlog(R.qm(p[j].q,R.qinv(q[j].q))))<1e-7,'authored rotations independent of future driven gait');}
 }
 // Once entry inertia expires, live left-arm locals are preserved exactly.
 for(let tick=101;tick<a.plan.endTick;tick+=.31){
  const f=H.sampleBody(a,tick/60),base=H.motion(data,'run',tick/60,saved.gazeYaw);
  for(const name of ['upperarm_l','lowerarm_l','hand_l']){const j=data.names.indexOf(name),parent=data.parents[j],rel=p=>R.qm(R.qinv(p[parent].q),p[j].q),err=R.length(R.qlog(R.qm(rel(f.pose),R.qinv(rel(base)))));maxLeftAngleError=Math.max(maxLeftAngleError,err);assert(err<1e-7,'live left arm local animation retained');}
 }
}
const receipt={passed:true,cases:2,maxDifferenceCm:maxDifference,maxLeftAngleErrorRadians:maxLeftAngleError};
fs.writeFileSync('Saved/Diagnostics/SwordPelvisAuthoring20261012/gait-isolation.json',JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
