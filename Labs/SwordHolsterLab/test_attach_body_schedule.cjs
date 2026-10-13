// Attaching the sword must not turn the torso speed ceiling into a new motion.
const assert=require('node:assert/strict'),H=require('./holster'),Body=require('./bodyreach'),Curve=require('./retime');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,samples=0,maxError=0;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const linear of [false,true]){
 // Keep an interior alignment tick even when the saved hand speeds finish in
 // one tick; otherwise there is no attachment body schedule to inspect.
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion,shrinkPercent:20,duration:8,maxAttachedRotationSpeed:60};
 if(linear)o.sheatheCurve=Curve.linear();
 const m=H.prepare(data,setup,o),curve=Curve.prepare(m.o.sheatheCurve),dock=m.tipAlign;
 assert(dock,'test must reach attachment');
 for(const f of m.frames.slice(dock.tick+1)){
  if(f.phase!=='Align tip')break;
  const elapsed=f.tick-m.o.startTick,reachTicks=m.plan.reachEndTick-m.o.startTick;
  const expected=Body.blend(f.body.entry,f.body.desired,Curve.sample(curve,elapsed/reachTicks));
  const error=Body.remaining(expected,f.body.applied);maxError=Math.max(maxError,error);
  assert(error<1e-4,`attachment changed body schedule: ${noCheat}/${motion}/${linear} tick ${f.tick}, ${error} degrees`);
  samples++;
 }
 cases++;
}
assert(samples>0);console.log(JSON.stringify({cases,samples,maxBodyScheduleErrorDegrees:maxError}));
