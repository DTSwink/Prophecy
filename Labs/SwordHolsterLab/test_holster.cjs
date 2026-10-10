const fs=require('fs'),assert=require('assert'),H=require('./holster.js'),R=require('./recovery.js');
const data=JSON.parse(fs.readFileSync(__dirname+'/data/motions.json')),setup=JSON.parse(fs.readFileSync(__dirname+'/data/unreal-setup.json'));
let count=0;
for(const motion of ['idle','walk'])for(const sheathe of [true,false])for(const shrinkPercent of [0,35,70]){
 const m=H.prepare(data,setup,{motion,sheathe,shrinkPercent,startTick:30,duration:6,spineClavicleAngleLimit:0});count++;
 assert.equal(m.frames[29].active,false);assert(m.frames[30].active);
 for(const [i,f] of m.frames.entries()){
  for(const t of [...f.pose,f.sword,f.holster])assert([...t.p,...t.q,...t.s].every(Number.isFinite));
  assert(Math.abs(f.sword.s[0]-setup.assetScale[0])<1e-8);assert(Math.abs(f.sword.s[1]-setup.assetScale[1])<1e-8);
  if(i>30&&f.phase==='Reach'&&m.frames[i-1].phase==='Reach'){
   const previous=m.frames[i-1],parent=data.parents[m.arm[0]];
   const localHand=frame=>({p:R.rotate(R.qinv(frame.pose[parent].q),R.sub(frame.pose[m.arm[2]].p,frame.pose[m.arm[0]].p)),q:R.qm(R.qinv(frame.pose[parent].q),frame.pose[m.arm[2]].q)});
   const a=localHand(previous),b=localHand(f);
   assert(R.length(R.sub(b.p,a.p))<=100/60+.01);
   assert(H.angle(b.q,a.q)<=180/60+.01);
  }
 }
 if(shrinkPercent===70)assert.equal(m.frames.at(-1).phase,sheathe?'Holstered':'Held');
 const a=H.sample(m,3.271);H.sample(m,.1);assert.deepEqual(a,H.sample(m,3.271));
 assert.deepEqual(m,H.prepare(data,setup,{motion,sheathe,shrinkPercent,startTick:30,duration:6,spineClavicleAngleLimit:0}));
}
const stalled=H.prepare(data,setup,{duration:8,shrinkPercent:0,spineClavicleAngleLimit:0});assert(stalled.frames.at(-1).blocked);
// Replay the measured Unreal stall geometry independently of the authored base clip.
const capture=JSON.parse(fs.readFileSync(__dirname+'/data/ue-stall-fixture.json')),bones=['upperarm_r','lowerarm_r','hand_r'];
const pose=bones.map(n=>({p:capture.nn[n],q:[0,0,0,1],s:[1,1,1]}));
const metrics=H.solve(pose,[0,1,2],{p:capture.goal,q:[0,0,0,1]});
assert(Math.abs(metrics.handError-(capture.nn_metrics.reach_shortfall+.001))<1e-5);
const report={passed:true,cases:count,deterministicSeeking:true,speedCaps:true,axisOnlyScale:true,ueMeasuredGeometryErrorCm:metrics.handError,referenceBladeCm:setup.bladeLength};
fs.writeFileSync(__dirname+'/../../Saved/Diagnostics/SwordHolsterLabQA/core.json',JSON.stringify(report,null,2));console.log(report);
