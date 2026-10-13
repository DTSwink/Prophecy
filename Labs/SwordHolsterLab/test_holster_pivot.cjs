const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,maxPivotError=0;
for(const noCheat of [false,true])for(const sheathe of [false,true])for(const holsterPivotPercent of [0,50,100]){
 const opts={...saved,...saved[sheathe?'sheatheBody':'drawBody'],sheathe,noCheat,motion:'run',holsterRotationStabilization:1,holsterPivotPercent,duration:10};
 const m=H.prepare(data,setup,opts),pivot=H.holsterPivot(setup,holsterPivotPercent),centre=H.prepare(data,setup,{...opts,holsterPivotPercent:50});
 assert(m.completionTick!==null);const grip=sheathe?m.plan.attachTick:m.plan.endTick;
 for(let x=0;x<m.frames.length-1;x+=.25){
  const f=H.sample(m,x/60),neutral=H.compose(m.holsterLocal,f.pose[m.pelvis]);
  const error=R.length(R.sub(H.point(f.holster,pivot),H.point(neutral,pivot)));
  maxPivotError=Math.max(maxPivotError,error);assert(error<1e-8,'selected pivot remains pelvis-attached at all sample times');
  if(Number.isInteger(x)&&x<=grip)assert.deepEqual(f.holster,centre.frames[x].holster,'pivot does not move neutral placement or jump on activation');
 }
 const last=m.frames.at(-1),neutral=H.compose(m.holsterLocal,last.pose[m.pelvis]);
 assert(R.length(R.sub(last.holster.p,neutral.p))<1e-8);assert(H.angle(last.holster.q,neutral.q)<1e-5);
 const off=H.prepare(data,setup,{...opts,holsterRotationStabilization:0}),offCentre=H.prepare(data,setup,{...opts,holsterRotationStabilization:0,holsterPivotPercent:50});
 assert.deepEqual(off.frames,offCentre.frames,'pivot has no effect when compensation is off');cases++;
}
assert.equal(H.sanitize({}).holsterPivotPercent,50);
console.log({cases,maxPivotErrorCm:maxPivotError,neutralAndReturnPreserved:true});
