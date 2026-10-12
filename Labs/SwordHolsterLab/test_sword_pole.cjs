const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js'),P=require('./elbowpole.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const dist=(a,b)=>R.length(R.sub(a,b)),rad=180/Math.PI;
let cases=0,maxSpeed=0,maxGrip=0,maxJump=0,maxEffect=0;
assert.equal(H.sanitize({}).swordRelativeSlidePole,false);
for(const motion of ['idle','walk','run'])for(const sheathe of [true,false])for(const early of [.7,1]){
 const action=sheathe?'sheathe':'draw',o=H.sanitize({...saved,motion,sheathe,duration:12,gazeYaw:0,maxElbowPoleAngularSpeed:25,swordRelativeSlidePole:false});
 o[action+'Return'].startFraction=early;o.bodyTargets.clear.pole=-40;o.bodyTargets.seated.pole=70;
 const off=H.prepare(data,setup,o),on=H.retime(off,{...o,swordRelativeSlidePole:true});
 assert(on.plan.arrives&&on.completionTick!==null,`${motion}/${action} completes`);
 assert.equal(on.sourceFrames,off.sourceFrames,'no new reach planning');assert.notEqual(on.poleGuides,off.poleGuides,'toggle invalidates pole cache');
 for(let t=0;t<on.plan.endTick/60;t+=.019){const a=H.sample(on,t).pose,b=H.sample(off,t).pose;for(let j=0;j<a.length;j++){assert(dist(a[j].p,b[j].p)<1e-8,'reach positions untouched');assert(R.length(R.qlog(R.qm(a[j].q,R.qinv(b[j].q))))<1e-8,'reach rotations untouched');}}
 const keys=on.poleGuides.keys,first=keys.find(k=>k.swordDown);assert.equal(first.tick,on.plan.endTick,'exact slide entry');
 let previous=null,basis=first.basis;
 for(let tick=on.plan.endTick;tick<=on.plan.slideEnd;tick+=.125){
  const t=tick/60,f=H.sample(on,t),ref={q:f.sword.q,down:first.swordDown};basis=P.frame(f.pose,on.arm,ref,basis);
  const angle=P.measure(f.pose,on.arm,ref,basis);
  if(previous!==null){const speed=Math.abs(P.wrap(angle-previous))*480;maxSpeed=Math.max(maxSpeed,speed);assert(speed<=25+1e-5,`sword-space speed ${speed}`);}previous=angle;
  maxGrip=Math.max(maxGrip,f.handError);assert(f.handError<.6,`grip ${f.handError} ${motion}/${action}/${early} tick ${tick} off ${H.sample(off,t).handError}`);
  const old=H.sample(off,t);maxEffect=Math.max(maxEffect,dist(f.pose[on.arm[1]].p,old.pose[on.arm[1]].p));
  for(const [a,b] of [[0,1],[1,2]])assert(Math.abs(dist(f.pose[on.arm[a]].p,f.pose[on.arm[b]].p)-dist(old.pose[on.arm[a]].p,old.pose[on.arm[b]].p))<1e-6,'length preserved');
 }
 for(const tick of [on.plan.endTick,on.plan.slideEnd]){
  const a=H.sample(on,tick/60-1e-7),b=H.sample(on,tick/60+1e-7);
  const jump=dist(a.pose[on.arm[1]].p,b.pose[on.arm[1]].p);maxJump=Math.max(maxJump,jump);assert(jump<.001,`phase seam ${jump}`);
 }
 for(const insertion of [0,.5,1]){const f=H.previewBody(on,insertion);assert.deepEqual(f.pose,H.sample(on,f.previewTime).pose,'preview matches playback');}
 const restored=H.retime(on,o);for(let t=0;t<off.playbackDuration;t+=.043)assert.deepEqual(H.sample(restored,t).pose,H.sample(off,t).pose,'uncheck restores existing motion');
 cases++;
}
assert(maxEffect>1,'option produces a meaningful sword-carried motion');
console.log(JSON.stringify({passed:true,cases,maxSpeed,maxGrip,maxJump,maxEffect}));


