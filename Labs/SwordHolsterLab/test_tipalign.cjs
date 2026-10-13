const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),Tip=require('./tipalign'),S=require('./sequence'),Curve=require('./retime');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const distance=(a,b)=>R.length(R.sub(a,b));
const localPoint=(p,f)=>R.rotate(R.qinv(f.holster.q),R.sub(p,f.holster.p));
let cases=0,unreachableCases=0,maxTip=0,maxGrip=0,maxLinear=0,maxAngular=0,maxFractionalGrip=0;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const curved of [false,true])for(const shrinkPercent of [0,20,65]){
 const curve=curved?[[.2,.03],[.4,.2],[.6,.8],[.8,.97]]:Curve.linear();
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion,shrinkPercent,duration:8,sheatheCurve:curve,sheatheSlideCurve:curve};
 const m=H.prepare(data,setup,o),dock=m.tipAlign,hand=m.arm[2];
 assert(dock,'rotation gate attaches');
 assert(m.plan.arrives&&m.completionTick!==null,'holster-owned sword finishes independently of arm reach');
 if(m.frames.some(f=>f.attached&&f.metrics.unreachable>.01))unreachableCases++;
 const alignEnd=m.plan.endTick;assert.equal(alignEnd,dock.tick+dock.ticks,'arm cannot delay tip arrival');const first=m.frames[dock.tick];
 const held=H.compose(H.scaledGrip(setup,first.scale),first.pose[hand]);
 assert(distance(first.sword.p,held.p)<1e-8&&H.angle(first.sword.q,held.q)<1e-5,'attachment preserves world transform');
 for(const f of m.frames.slice(o.startTick,dock.tick))assert(H.angle(f.sword.q,H.seatedSword(setup,f.holster).q)>o.sheatheRotationTolerance,'capture at the FIRST green tick');
 for(let tick=dock.tick;tick<=alignEnd;tick++){
  const f=m.frames[tick],full=H.seatedSword(setup,f.holster);
  assert.equal(f.scale,dock.scale,'freeze shrink during alignment');
  if(tick===alignEnd)assert(Math.abs(f.insertion-dock.insertion)<1e-10,'start at captured depth');
  assert(H.angle(f.sword.q,full.q)<=o.sheatheRotationTolerance+1e-5,'stay inside full rotation ball');
  const held=H.compose(H.scaledGrip(setup,f.scale),f.pose[hand]),grip=distance(f.sword.p,held.p);maxGrip=Math.max(maxGrip,grip);
  const expected=Tip.sample(H,setup,m.tip,dock,f.holster,tick);
  assert(distance(f.sword.p,expected.sword.p)<1e-8&&H.angle(f.sword.q,expected.sword.q)<1e-5,'sword follows its holster-local path, not the solved hand');
  assert(Math.abs(f.handError-distance(f.pose[hand].p,f.goal.p))<1e-8,'report the actual grip tracking gap');
  assert(!f.blocked,'unreachable hand does not block the attached sword');
  if(tick>dock.tick){
   const prev=m.frames[tick-1],speed=distance(localPoint(f.goal.p,f),localPoint(prev.goal.p,prev))*60;
   const omega=H.angle(R.qm(R.qinv(f.holster.q),f.goal.q),R.qm(R.qinv(prev.holster.q),prev.goal.q))*60;
   maxLinear=Math.max(maxLinear,speed/m.o.maxAttachedSpeed);maxAngular=Math.max(maxAngular,omega/m.o.maxAttachedRotationSpeed);
   assert(speed<=m.o.maxAttachedSpeed+1e-6&&omega<=m.o.maxAttachedRotationSpeed+1e-3,'independent attached hand translation and rotation caps in holster frame');
  }
 }
 if(m.plan.arrives){
 const end=m.frames[m.plan.endTick],tipError=distance(H.point(end.sword,m.tip),R.add(end.holster.p,R.rotate(end.holster.q,dock.tipLocal)));
 maxTip=Math.max(maxTip,tipError);assert(tipError<1e-8,'slide starts with tip at preserved depth on the insertion axis');
 const full=H.seatedSword(setup,first.holster),axis=R.rotate(R.qm(R.qinv(first.holster.q),full.q),[0,0,1]);
 assert(Math.abs(R.dot(R.sub(dock.endHand,dock.startHand),axis))<1e-8,'alignment does not reset grip depth');
 const final=m.frames[m.plan.slideEnd];assert(Math.abs(final.insertion-1)<1e-10,'fully seated at completion');
 const capture=Tip.sample(H,setup,m.tip,dock,first.holster,dock.tick),endAlign=Tip.sample(H,setup,m.tip,dock,end.holster,m.plan.endTick);
 assert(distance(capture.sword.p,first.sword.p)<1e-8&&distance(endAlign.sword.p,end.sword.p)<1e-8,'both boundaries continuous');}
 for(let t=dock.tick+.25;t<dock.tick+dock.ticks;t+=.5){
  const f=H.sample(m,t/60);const grip=localPoint(f.goal.p,f),expected=R.add(dock.startHand,R.mul(R.sub(dock.endHand,dock.startHand),dock.translationTicks>0?Math.min(1,(t-dock.tick)/dock.translationTicks):1));
  assert(distance(grip,expected)<1e-8,'fractional playback stays holster-local');
  maxFractionalGrip=Math.max(maxFractionalGrip,distance(f.pose[hand].p,f.goal.p));
 }
 // Changing render sample order cannot advance/reset the attachment state.
 assert.deepEqual(H.sample(m,(dock.tick+.5)/60),H.sample(m,(dock.tick+.5)/60));cases++;
}
for(const noCheat of [false,true])for(const sheathe of [false,true]){
 const m=S.prepare(data,setup,{...saved,noCheat,sheathe,motion:'run',sequenceMode:true,duration:8});
 assert(m.sequence.second?.completionTick!==null);const part=sheathe?m.sequence.first:m.sequence.second;assert(part.tipAlign&&part.plan.arrives);
}
assert(unreachableCases>0,'include arm reach failures without hiding their grip gap');
console.log(JSON.stringify({pass:true,cases,unreachableCases,maxTip,maxGrip,maxLinearRatio:maxLinear,maxAngularRatio:maxAngular,maxFractionalGrip},null,2));
