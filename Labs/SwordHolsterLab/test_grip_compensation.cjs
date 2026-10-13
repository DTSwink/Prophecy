const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),P=require('./sequence');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,maxError=0;
function check(m){
 assert(m.completionTick!==null,'action and mount return complete');
 const o=m.o,grip=o.sheathe?m.plan.attachTick:m.plan.endTick,release=m.plan.slideEnd,returnTicks=Math.ceil(o.holsterReturnDuration*60-1e-5);
 const neutral=f=>H.compose(m.holsterLocal,H.motion(data,o.motion,m.motionOffset+f.tick/60,o.gazeYaw)[m.pelvis]);
 const capture=neutral(m.frames[grip]).q;
 for(const f of m.frames){
  const n=neutral(f),fade=f.tick<=release?1:returnTicks>0?Math.max(0,1-(f.tick-release)/returnTicks):0;
  const weight=f.tick<grip?0:o.holsterRotationStabilization*fade,expected=R.qslerp(n.q,capture,weight);
  const error=H.angle(f.holster.q,expected);maxError=Math.max(maxError,error);assert(error<1e-4,'phase/captured-frame/return weight');
  assert(R.length(R.sub(f.holster.p,n.p))<1e-9,'translation stays on original pelvis mount');
  if(f.tick>=release+Math.max(1,returnTicks))assert.deepEqual(f.holster,n,'exact neutral mount restored');
 }
 assert(H.angle(m.frames[grip].holster.q,capture)<1e-5,'activation has no rotation snap');
 if(o.holsterRotationStabilization>0)assert(m.completionTick>=release+Math.max(1,returnTicks),'timeline includes full mount return');
 const t=(grip+.5)/60;assert.deepEqual(H.sample(m,t),H.sample(m,t),'scrubbing does not advance state');cases++;
}
for(const noCheat of [false,true])for(const sheathe of [false,true])for(const motion of ['walk','run'])for(const amount of [0,.4,1]){
 check(H.prepare(data,setup,{...saved,...saved[sheathe?'sheatheBody':'drawBody'],sheathe,noCheat,motion,holsterRotationStabilization:amount,holsterReturnDuration:.25,duration:10}));
}
for(const sheathe of [false,true])for(const duration of [0,1.5])check(H.prepare(data,setup,{...saved,...saved[sheathe?'sheatheBody':'drawBody'],sheathe,noCheat:true,motion:'run',holsterRotationStabilization:1,holsterReturnDuration:duration,duration:10}));
for(const sheathe of [false,true]){
 const m=P.prepare(data,setup,{...saved,sheathe,noCheat:true,motion:'run',holsterRotationStabilization:1,holsterReturnDuration:.8,duration:10,sequenceMode:true});
 assert(m.sequence.second,'second action starts after return');check(m.sequence.first);check(m.sequence.second);
 assert(H.angle(m.sequence.first.frames.at(-1).holster.q,m.sequence.second.frames[0].holster.q)<1e-5,'sequence join has no mount reset');
}
console.log(JSON.stringify({cases,maxRotationErrorDegrees:maxError,activationContinuous:true,exactMountRestored:true,sequenceBothOrders:true}));
