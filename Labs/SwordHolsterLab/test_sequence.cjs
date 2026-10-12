const assert=require('node:assert/strict'),S=require('./sequence.js'),H=require('./holster.js'),R=require('./recovery.js'),T=require('./retime.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json');
const qdist=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),pdist=(a,b)=>R.length(R.sub(a,b));
let cases=0,maxJoinPosition=0,maxJoinRotation=0,maxBaseError=0;
for(const motion of ['idle','walk','run'])for(const curved of [false,true])for(const sheathe of [true,false]){
 const p=saved.parameters,curve=curved?[[.2,.06],[.4,.2],[.6,.85],[.8,.96]]:T.linear();
 const o={...p,sequenceMode:true,sheathe,motion,drawCurve:curve,sheatheCurve:curve,drawSlideCurve:curve,sheatheSlideCurve:curve};
 const m=S.prepare(data,setup,o),{first,second,offset}=m.sequence;
 assert(first.completionTick!==null&&second?.completionTick!==null,'both actions complete');
 assert.deepEqual(first.o.bodyTargets,H.sanitize({...o,...o[sheathe?'sheatheBody':'drawBody']}).bodyTargets,'S uses its saved targets');
 assert.deepEqual(second.o.bodyTargets,H.sanitize({...o,...o[sheathe?'drawBody':'sheatheBody']}).bodyTargets,'D uses its saved targets');
 assert.equal(offset,first.completionTick/60);assert.equal(second.motionOffset,offset);assert.equal(second.o.startTick,0,'no second start delay');
 assert.equal(m.frames.length,m.completionTick+1);assert.equal(m.playbackDuration,offset+second.playbackDuration);
 const a=H.sample(first,offset),b=H.sample(second,0);
 assert(!a.active&&a.headLook.done,'first return and head complete before second action');
 assert.equal(S.sample(m,0).sequenceAction,sheathe?'S':'D');assert.equal(S.sample(m,offset).sequenceAction,sheathe?'D':'S');
 assert.deepEqual(S.retime(m,{...o,sheathe:!sheathe}).frames,S.prepare(data,setup,{...o,sheathe:!sheathe}).frames,'changing order through retime rebuilds both actions');
 for(let j=0;j<data.names.length;j++){
  maxJoinPosition=Math.max(maxJoinPosition,pdist(a.pose[j].p,b.pose[j].p));maxJoinRotation=Math.max(maxJoinRotation,qdist(a.pose[j].q,b.pose[j].q));
  assert(pdist(a.pose[j].p,b.pose[j].p)<.001&&qdist(a.pose[j].q,b.pose[j].q)<1e-4,JSON.stringify({motion,curved,sheathe,bone:data.names[j],p:pdist(a.pose[j].p,b.pose[j].p),q:qdist(a.pose[j].q,b.pose[j].q),offset}));
 }
 assert(pdist(a.sword.p,b.sword.p)<1e-8&&qdist(a.sword.q,b.sword.q)<1e-8,'continuous sword/parenting');
 for(let t=0;t<m.playbackDuration;t+=.043){
  const f=S.sample(m,t),part=S.segment(m,t),base=H.motion(data,motion,t,o.gazeYaw);
  for(let j=0;j<data.names.length;j++)if(!part.model.fkReturn.model.upper[j]){
   const e=pdist(f.pose[j].p,base[j].p);maxBaseError=Math.max(maxBaseError,e);assert(e<1e-8&&qdist(f.pose[j].q,base[j].q)<1e-8,'locomotion runs on global time');
  }
  assert.deepEqual(S.sample(m,t),f,'stateless scrubbing');
 }
 for(const sheathe of [true,false])for(const insertion of [0,1]){
  const part=S.edited(m,sheathe),time=S.previewTime(m,insertion,sheathe);
  assert.equal(time,part.offset+H.previewTime(part.model,insertion));
  const preview=S.previewBody(m,insertion,part.model.o.bodyTargets,time,sheathe),f=S.sample(m,time);assert.deepEqual(preview.pose,f.pose,'endpoint preview samples selected sequence part');
 }
 const returnKey=sheathe?'sheatheReturn':'drawReturn';
 const changed={...o,[returnKey]:{...o[returnKey],duration:1.8}},retimed=S.retime(m,changed);
 assert(retimed.sequence.second.motionOffset===retimed.sequence.first.playbackDuration,'changed S deadline carries into D locomotion');
 assert(retimed.sequence.first.sourceFrames===first.sourceFrames,'retiming reuses first source plan');
 const same=S.retime(m,o);assert(same.sequence.second.sourceFrames===second.sourceFrames,'unchanged offset reuses second plan');
 const clone=structuredClone(S.assets(m));assert(!clone.sequence.first.data&&!clone.sequence.second.data);S.assets(m,data,setup);S.assets(clone,data,setup);
 assert.deepEqual(S.sample(clone,offset+.1),S.sample(m,offset+.1),'worker asset reattachment');
 cases++;
}
const offOptions={...saved.parameters,sequenceMode:false},off=S.prepare(data,setup,offOptions),plain=H.prepare(data,setup,offOptions);assert.deepEqual(off.frames,plain.frames,'standalone unchanged');
for(const sheathe of [true,false]){const key=sheathe?'sheatheReturn':'drawReturn';const disabled=S.prepare(data,setup,{...saved.parameters,sheathe,sequenceMode:true,[key]:{...saved.parameters[key],enabled:false}});assert(!disabled.sequence.second&&disabled.sequence.reason.includes('Enable'),'does not skip disabled full return');}
const short=S.prepare(data,setup,{...saved.parameters,sequenceMode:true,duration:1,startTick:55});assert(!short.sequence.second&&short.sequence.reason,'does not draw after a truncated sheath');
console.log(JSON.stringify({passed:true,cases,maxJoinPosition,maxJoinRotation,maxBaseError}));
