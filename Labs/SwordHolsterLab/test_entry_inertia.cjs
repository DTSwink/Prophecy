const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const linear=[[.2,.2],[.4,.4],[.6,.6],[.8,.8]],curve=[[.2,.03],[.4,.2],[.6,.8],[.8,.97]],dt=1e-5;
const distance=(a,b)=>R.length(R.sub(a,b));
function velocityError(m){
 const start=m.o.startTick/60,frames=[start-dt,start,start+dt].map(t=>{
  const p=H.sample(m,t).pose,a=p[m.pelvis],b=p[m.arm[2]];
  return {p:R.rotate(R.qinv(a.q),R.sub(b.p,a.p)),q:R.qm(R.qinv(a.q),b.q)};
 });
 const velocity=(a,b)=>({p:R.mul(R.sub(b.p,a.p),1/dt),q:R.mul(R.qlog(R.qm(b.q,R.qinv(a.q))),180/Math.PI/dt)});
 const a=velocity(frames[0],frames[1]),b=velocity(frames[1],frames[2]);
 return {linear:distance(a.p,b.p),angular:distance(a.q,b.q)};
}
const reports=[];
for(const motion of ['idle','walk','run'])for(const sheathe of [true,false])for(const curved of [false,true]){
 const action=sheathe?'sheathe':'draw',off=H.prepare(data,setup,{...saved,motion,sheathe,startTick:70,gazeYaw:0,entryInertia:0,[action+'Curve']:curved?curve:linear,[action+'SlideCurve']:linear});
 const on=H.retime(off,{...off.o,entryInertia:1,entryInertiaDuration:.2});
 assert.equal(on.sourceFrames,off.sourceFrames,'entry control reuses planned path');
 assert.equal(on.plan,off.plan,'entry inertia leaves arrival checks and slide timing intact');
 const before=velocityError(off),after=velocityError(on);
 assert(after.angular<.2,`angular momentum follows incoming arm ${motion} ${sheathe} ${curved}: ${after.angular}`);
 assert(after.linear<before.linear*.2,`hand velocity discontinuity reduced ${motion} ${sheathe} ${curved}: ${JSON.stringify({before,after})}`);
 const start=on.o.startTick/60,end=start+on.entryInertia.duration;
 const localAt=t=>{const p=H.sampleBody(on,t).pose;return R.localize(p.map(v=>v.p),p.map(v=>v.q),on.parents);};
 const local=[localAt(start-dt),localAt(start),localAt(start+dt)];
 for(const j of on.bodyContext.inertiaBones){
  const incoming=R.mul(R.qlog(R.qm(R.qinv(local[0].q[j]),local[1].q[j])),1/dt),outgoing=R.mul(R.qlog(R.qm(R.qinv(local[1].q[j]),local[2].q[j])),1/dt);
  assert(distance(incoming,outgoing)<.01,`entry local angular velocity continuous through ${on.names[j]}`);
 }
 assert.deepEqual(H.sample(on,start).pose,H.sample(off,start).pose,'no entry pose jump');
 for(const t of [end,end+.1,on.plan.endTick/60])assert.deepEqual(H.sampleBody(on,t).pose,H.sampleBody(off,t).pose,'exact original FK after fade');
 for(let t=start+.003;t<end;t+=.013){
  const a=H.sampleBody(on,t),b=H.sampleBody(off,t);
  for(let j=0;j<data.names.length;j++){
   const p=data.parents[j];if(p>=0)assert(Math.abs(distance(a.pose[j].p,a.pose[p].p)-distance(b.pose[j].p,b.pose[p].p))<1e-7,'FK segment lengths preserved');
   if(!on.bodyContext.affected.includes(j))assert.deepEqual(a.pose[j],b.pose[j],'pelvis and legs untouched');
  }
  if(sheathe){const sword=H.compose(H.scaledGrip(setup,a.scale),a.pose[on.arm[2]]);assert(distance(sword.p,a.sword.p)<1e-8,'held sword follows inertial hand');}
 }
 const zero=H.retime(off,{...off.o,entryInertia:1,entryInertiaDuration:0});assert.equal(zero.entryInertia,null,'zero duration disables work');
 reports.push({motion,sheathe,curved,before,after});
}
console.log(JSON.stringify({passed:true,cases:reports.length,reports},null,2));
