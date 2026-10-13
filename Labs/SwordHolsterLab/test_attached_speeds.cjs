const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0;
for(const noCheat of [false,true]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion:'run',duration:8};
 const baseline=H.prepare(data,setup,o);
 for(const maxAttachedSpeed of [30,230])for(const maxAttachedRotationSpeed of [40,600]){
  const m=H.prepare(data,setup,{...o,maxAttachedSpeed,maxAttachedRotationSpeed}),a=m.tipAlign,b=baseline.tipAlign;
  assert.deepEqual(m.frames.slice(0,a.tick),baseline.frames.slice(0,b.tick),'attached knobs cannot change approach');
  assert.deepEqual(a.startHand,b.startHand);assert.deepEqual(a.endHand,b.endHand);assert.deepEqual(a.endQ,b.endQ);
  assert(Math.abs(a.translationTicks-R.length(R.sub(a.endHand,a.startHand))*60/maxAttachedSpeed)<1e-10);
  assert(Math.abs(a.rotationTicks-H.angle(a.local.q,a.endQ)*60/maxAttachedRotationSpeed)<1e-10);
  assert.equal(m.plan.endTick,a.tick+a.ticks);assert(m.completionTick!==null);cases++;
 }
 const draws=[40,600].map(maxAttachedRotationSpeed=>H.prepare(data,setup,{...o,sheathe:false,maxAttachedSpeed:maxAttachedRotationSpeed,maxAttachedRotationSpeed}).frames);
 assert.deepEqual(draws[0],draws[1],'attached alignment knobs do not change drawing');
}
const migrated=H.sanitize({maxReachSpeed:260,maxReachRotationSpeed:900,sheatheBody:{maxReachSpeed:230,maxReachRotationSpeed:600}});
assert.equal(migrated.maxAttachedSpeed,230);assert.equal(migrated.maxAttachedRotationSpeed,600);
console.log(JSON.stringify({cases,independentSpeeds:true,approachAndDrawingUnchanged:true,migratesSheathingValues:true}));
