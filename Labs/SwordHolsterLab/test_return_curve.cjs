const assert=require('node:assert/strict'),H=require('./holster'),F=require('./fkreturn'),T=require('./retime'),R=require('./recovery'),P=require('./sequence');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const slow=[[.2,.02],[.4,.12],[.6,.35],[.8,.7]],fast=[[.2,.4],[.4,.7],[.6,.88],[.8,.97]];
const distance=(a,b)=>R.length(R.sub(a,b));
assert.deepEqual(F.sanitize({}).timingCurve,T.linear());
assert.deepEqual(F.sanitize({timingCurve:[[NaN,0]]}).timingCurve,T.linear());
assert.notEqual(H.sanitize({}).drawReturn.timingCurve,H.sanitize({}).sheatheReturn.timingCurve);
let cases=0,changed=0,maxGrip=0;
for(const noCheat of [false,true])for(const sheathe of [false,true])for(const springReturn of [false,true]){
 const action=sheathe?'sheathe':'draw',o={motion:'walk',sheathe,noCheat,duration:12,[action+'Return']:{...F.defaults(),duration:.65,startFraction:.9,springReturn}};
 const linear=H.prepare(data,setup,o),m=H.retime(linear,{...linear.o,[action+'Return']:{...linear.o[action+'Return'],timingCurve:slow}});
 assert(linear.fkReturn&&m.fkReturn&&m.completionTick,'action completes');
 assert.equal(m.fkReturn.start,linear.fkReturn.start);assert.equal(m.fkReturn.timing.duration,linear.fkReturn.timing.duration);
 assert.equal(m.plan.slideEnd,linear.plan.slideEnd,'curve does not retime sliding');
 for(const ret of [m.fkReturn,m.armReturn].filter(Boolean)){
  const base=H.motion(data,o.motion,ret.start+.3),old={...ret,curve:T.prepare(T.linear())};
  for(const u of [0,.1,.4,.7,.999,1]){
   const elapsed=ret.timing.duration*u,warped=T.time(ret.curve,elapsed,0,ret.timing.duration);
   assert.deepEqual(F.sample(ret,base,elapsed),F.sample(old,base,warped),'only return residual is retimed against current base');
  }
  assert.deepEqual(F.sample(ret,base,ret.timing.duration),base,'exact destination');
 }
 for(let i=0;i<m.frames.length;i++){
  const frame=m.frames[i],t=i/60,base=H.motion(data,o.motion,t);
  for(let j=0;j<data.names.length;j++){
   assert(frame.pose[j].p.every(Number.isFinite)&&frame.pose[j].q.every(Number.isFinite));
   if(!m.fkReturn.model.upper[j])assert(distance(frame.pose[j].p,base[j].p)<1e-7,'base motion clock unchanged');
  }
  if(t<m.fkReturn.start-1e-8)assert.deepEqual(frame.pose,linear.frames[i].pose,'pre-return unchanged');
  if(frame.fkReturn?.gripping){maxGrip=Math.max(maxGrip,frame.handError);assert(distance(frame.sword.p,linear.frames[i].sword.p)<1e-7,'return cannot move the held sword off its slide path');}
  if(t>m.plan.slideEnd/60&&linear.frames[i]&&H.angle(frame.pose[m.arm[2]].q,linear.frames[i].pose[m.arm[2]].q)>.01)changed++;
 }
 cases++;
}
assert(changed>0,'curve visibly changes return motion');
for(const sheathe of [false,true]){
 const options={sheathe,sequenceMode:true,duration:12,drawReturn:{...F.defaults(),timingCurve:fast},sheatheReturn:{...F.defaults(),timingCurve:slow}};
 const m=P.prepare(data,setup,options);assert(m.sequence.second&&m.completionTick,'sequence completes');
 for(const part of [m.sequence.first,m.sequence.second])assert.deepEqual(part.fkReturn.options.timingCurve,part.o.sheathe?slow:fast,'sequence retains independent return curves');
}
console.log(JSON.stringify({passed:true,cases,sequences:2,changed,maxGrip}));
