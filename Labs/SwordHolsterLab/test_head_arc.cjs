const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),fixture=require('./data/owl-regression.json');
const model=H.prepare(data,setup,fixture),head=model.headContext.head;
let previous=null,peakChange=0;
for(let tick=98;tick<=112;tick++){
 const frame=model.frames[tick],before=model.frames[tick-1];
 const velocity=R.mul(R.qlog(R.qm(frame.pose[head].q,R.qinv(before.pose[head].q))),180/Math.PI);
 assert(!('boundaryLimited' in frame.headLook)&&!('targetLimited' in frame.headLook),'no anatomical limit masks rotation errors');
 if(previous){
  assert(R.dot(previous,velocity)>0,'head must not reverse at the 180-degree interpolation crossing');
  const change=R.length(R.sub(velocity,previous));peakChange=Math.max(peakChange,change);
  assert(change<.2,'no angular-velocity jump');
  assert(R.length(velocity)<R.length(previous),'profile continues decelerating');
 }
 previous=velocity;
}
for(let tick=103;tick<110;tick+=.125){
 const a=H.sample(model,tick/60),b=H.sample(model,(tick+.125)/60);
 assert(H.angle(a.pose[head].q,b.pose[head].q)<.2,'smooth fractional playback through the reported interval');
 assert.deepEqual(H.sample(model,tick/60),a,'seeking is deterministic');
}
// Separate parent/head distribution changes the moving eye position slightly.
assert.equal(model.completionTick,298);
console.log(JSON.stringify({passed:true,interval:[98,112],peakVelocityChangeDegreesPerTick:peakChange}));
