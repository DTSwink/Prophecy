const assert=require('node:assert/strict'),H=require('./holster.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const legacy=H.sanitize({maxHeadLookInVelocity:320,maxHeadLookOutVelocity:110,headLookInExponent:2,headLookOutExponent:3});
assert.equal(legacy.maxHeadLookInVelocityAtMaxGaze,320);assert.equal(legacy.maxHeadLookOutVelocityAtMaxGaze,110);
const options=H.sanitize({...legacy,maxHeadLookInVelocityAtMaxGaze:640,maxHeadLookOutVelocityAtMaxGaze:330});
for(const gaze of [-170,-85,0,85,170]){
 const alpha=Math.abs(gaze)/170;
 assert.equal(H.headSpeed(options,false,gaze),320+320*alpha);
 assert.equal(H.headSpeed(options,true,gaze),110+220*alpha);
}
for(const sheathe of [false,true])for(const gazeYaw of [-85,0,85,170]){
 const m=H.prepare(data,setup,{...options,sheathe,gazeYaw,duration:15});
 for(const f of m.frames.filter(f=>f.tick>m.o.startTick)){
  const out=['Look out','Forward'].includes(f.headLook.mode),speed=H.headSpeed(m.o,out,gazeYaw);
  assert.equal(f.headLook.speedLimit,speed);
  assert(f.headLook.angularStep<=speed/60+.001);
 }
 assert.equal(m.o.headLookInExponent,2);assert.equal(m.o.headLookOutExponent,3);
 assert(m.completionTick!==null);
}
console.log('PASS: gaze speed endpoints, symmetric interpolation, legacy tuning migration, shared exponents and per-tick angular limits.');
