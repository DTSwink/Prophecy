const assert=require('node:assert/strict'),H=require('./holster.js'),B=require('./bodyreach.js'),L=require('./headlook.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),I=[0,0,0,1],ctx=L.make(data),dist=(a,b)=>R.length(R.sub(a,b));
assert(!('headCorrectionAlpha' in H.sanitize({headCorrectionAlpha:.7})));
assert.equal(H.defaults.drawHeadLookOutThreshold,.3);assert.equal(H.defaults.sheatheHeadLookOutThreshold,.5);
const reports=[];
for(const motion of ['idle','walk'])for(const sheathe of [false,true]){
 const m=H.prepare(data,setup,{motion,sheathe}),bc=B.make(data,H.motion(data,motion,0));
 const threshold=sheathe?.5:.3,expected=m.plan.endTick+Math.ceil((m.plan.slideEnd-m.plan.endTick)*threshold);
 assert.equal(m.frames.find(f=>['Look out','Forward'].includes(f.headLook.mode)).tick,expected);
 assert(m.frames[m.plan.endTick-1].headLook.aimErrorDegrees<.01,'aim reaches moving holster before grip');
 for(const f of m.frames){
  const base=H.motion(data,motion,f.tick/60);
  if(f.tick<=m.o.startTick){for(const j of ctx.chain){assert(dist(f.pose[j].p,base[j].p)<1e-8);assert(H.angle(f.pose[j].q,base[j].q)<1e-5);}continue;}
  assert(f.headLook.angularStep<=f.headLook.speedLimit/60+.001,'head speed cap');
  const inherited=H.sampleBody(m,f.tick/60).pose,correction=R.qm(f.pose[ctx.head].q,R.qinv(inherited[ctx.head].q));
  assert.deepEqual(f.pose[ctx.anchor],inherited[ctx.anchor],'spine_05 untouched');
  for(const [k,j] of ctx.chain.entries()){
   const net=R.qm(f.pose[j].q,R.qinv(inherited[j].q));
   assert(H.angle(net,R.qslerp(I,correction,(k+1)/3))<1e-5,'neck net shares 1/3, 2/3, head 1');
   assert(Math.abs(dist(f.pose[j].p,f.pose[data.parents[j]].p)-dist(inherited[j].p,inherited[data.parents[j]].p))<1e-6,'head overlay preserves incoming FK bone length');
  }
  const full=H.compose(setup.seated,f.holster),mouth=R.add(full.p,R.rotate(full.q,setup.baseBladeLocal.map((v,j)=>v*full.s[j])));
  assert(dist(f.headLook.target,mouth)<1e-9,'uses actual blade-base mouth, not grip');
 }
 assert(m.frames.at(-1).headLook.done);assert(H.angle(m.frames.at(-1).pose[ctx.head].q,H.motion(data,motion,m.playbackDuration)[ctx.head].q)<.001);
 reports.push({motion,sheathe,lookOutTick:expected,completionTick:m.completionTick});
}
for(const sheathe of [false,true])for(const threshold of [0,1]){
 const m=H.prepare(data,setup,{sheathe,[sheathe?'sheatheHeadLookOutThreshold':'drawHeadLookOutThreshold']:threshold});
 const f=m.frames.find(f=>['Look out','Forward'].includes(f.headLook.mode));
 assert.equal(f.tick,threshold===0?m.plan.endTick:m.plan.slideEnd,'threshold endpoints');
 if(threshold===1)assert(m.completionTick>m.plan.slideEnd,'return visible after slide ends');
}
const base=H.prepare(data,setup,{}),slow=H.prepare(data,setup,{maxHeadLookInVelocity:12,maxHeadLookOutVelocity:8,drawHeadLookOutThreshold:1,sheatheHeadLookOutThreshold:1});
assert.equal(slow.completionTick,null,'slow return stays active until configured end');
assert(slow.frames[slow.plan.endTick].headLook.aimErrorDegrees>10,'slow look-in never snaps');
assert.equal(slow.frames.at(-1).headLook.mode,'Look out');
for(let i=0;i<base.frames.length;i++){
 for(let j=0;j<data.names.length;j++)if(!ctx.chain.includes(j))assert.deepEqual(slow.frames[i].pose[j],base.frames[i].pose[j],'head controls leave body/arm alone');
 assert.deepEqual(slow.frames[i].sword,base.frames[i].sword);
}
assert.equal(H.defaults.headLookAtAlpha,1);
assert.equal(H.sanitize({headLookAtAlpha:-1}).headLookAtAlpha,0);assert.equal(H.sanitize({headLookAtAlpha:2}).headLookAtAlpha,1);
for(const alpha of [0,.5]){
 const m=H.prepare(data,setup,{headLookAtAlpha:alpha}),f=m.frames[m.plan.endTick-1],forward=H.motion(data,m.o.motion,f.tick/60)[ctx.head].q;
 const aim=R.qm(R.fromTo(R.rotate(forward,[0,1,0]),R.sub(f.headLook.target,f.pose[ctx.head].p)),forward);
 assert(H.angle(f.pose[ctx.head].q,R.qslerp(forward,aim,alpha))<.001,'look-at alpha weights aiming from forward');
 assert.deepEqual(f.sword,base.frames[f.tick].sword,'alpha does not affect sword');
}
console.log(JSON.stringify({passed:true,cases:reports,checks:'aim, head speeds, distributed neck, fixed anchor, independent thresholds, endpoint triggers, slow return, body/equipment preservation'},null,2));
