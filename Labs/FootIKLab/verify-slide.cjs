const fs=require('fs'),z=require('zlib'),assert=require('assert/strict');
const F=require('./surface.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const checks=[],cases=[],check=(name,value)=>{assert(value,name);checks.push(name);};
(async()=>{
 check('Slide is opt-in and has bounded timing',!K.sanitize().slideEnabled&&K.sanitize().slideSpeed===2&&K.sanitize({slideBlend:0}).slideBlend===.05);
 const run=load('walk',.21),base={gait:'walk',minGravityIncline:80,pelvisCloser:10};
 for(const slopeAngle of [0,80]){const off=F.prepare(run,{...base,slopeAngle}),on=F.prepare(run,{...base,slopeAngle,slideEnabled:true,slideSpeed:0});check('No slide at/below dangerous minimum '+slopeAngle,JSON.stringify(off.frames)===JSON.stringify(on.frames));}
 for(const slopeAngle of [85,90]){const m=F.prepare(run,{...base,slopeAngle,slideEnabled:true,slideSpeed:.5,inclineGravity:true}),frames=m.frames.filter(f=>f.slide);check('Intermediate incline triggers '+slopeAngle,frames.length>0);check('No mover force on incline '+slopeAngle,frames.every(f=>R.length(f.surface.drive)===0&&R.length(f.surface.supportForce)===0&&f.surface.acceleration[1]===-9.81));}
 for(const threshold of [2,5]){
  const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(`snapshots/slide-live-${threshold}.json.gz`))),run=K.decode(request.source,require('./data/rig.json').parents),{model}=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);
  const start=model.frames.findIndex(f=>f.slide),entry=model.frames[start],end=model.frames.at(-1),ready=model.frames.filter(f=>f.slide?.blend===1);
  check(threshold+' triggers only once on a dangerous surface',model.events.filter(e=>e.type==='slide').length===1&&Math.abs(entry.surface.velocity[1])>=threshold&&Math.acos(entry.surface.pinNormal[1])*180/Math.PI>model.settings.minGravityIncline);
  check(threshold+' latches to end and cancels material pins',model.frames.slice(start).every(f=>f.surface.mode==='SLIDE'&&!f.surface.pinsAllowed&&f.feet.every(x=>x.contact===null)));
  check(threshold+' uses gravity only, irrespective of full-gravity percentage',model.frames.slice(start).every(f=>R.length(f.surface.drive)===0&&R.length(f.surface.supportForce)===0&&R.length(R.sub(f.surface.acceleration,[0,-9.81,0]))===0));
  check(threshold+' does not restart energy-transfer thrust',!model.events.some(e=>e.type==='root-transfer'&&e.frame>=start/2));
  check(threshold+' stops requesting unused locomotion inference',model.coupling.windows.every(w=>w.frame<start/2)&&model.coupling.steps<149);
  let velocityError=0,positionError=0,boneError=0,replayError=0,soleGap=0,handGap=0,penetration=0,kneeStep=0;
  const handSides=new Set();
  for(let i=start;i<model.frames.length;i++){
   const f=model.frames[i],p=f.pose;handSides.add(f.slide.hand.side);
   if(i+1<model.frames.length){const next=model.frames[i+1].surface,v=R.add(f.surface.velocity,R.add(R.mul(f.surface.acceleration,1/120),f.surface.collisionImpulse));velocityError=Math.max(velocityError,R.length(R.sub(v,next.velocity)));const mass=R.add(f.surface.mass,R.add(R.mul(R.add(f.surface.velocity,R.mul(f.surface.acceleration,1/120)),1/120),f.surface.collisionCorrection));positionError=Math.max(positionError,R.length(R.sub(mass,next.mass)));}
   for(let j=2;j<run.names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(R.sub(p.points[j],p.points[run.parents[j]]))-R.length(R.sub(entry.pose.points[j],entry.pose.points[run.parents[j]]))));
   penetration=Math.max(penetration,...f.feet.map(x=>x.penetration));
   if(f.slide.blend===1){soleGap=Math.max(soleGap,...f.feet.map(x=>Math.abs(x.soleGap)));handGap=Math.max(handGap,f.slide.hand.gap);}
   if(i>start)for(const side of ['L','R']){const l=S.leg(p,run.names,side);kneeStep=Math.max(kneeStep,R.length(R.qlog(R.qm(p.q[l.knee],R.qinv(model.frames[i-1].pose.q[l.knee]))))*180/Math.PI);}
  }
  for(const w of model.coupling.windows){const actual=response.diagnostics.coupling.windows.find(x=>x.frame===w.frame);replayError=Math.max(replayError,R.length(R.sub(actual.root,w.root)),R.length(R.sub(actual.velocity,w.velocity)));}
  check(threshold+' preserves inertia and integrates ballistic motion',velocityError<1e-10&&positionError<1e-10);
  check(threshold+' same hand throughout slide',handSides.size===1);
  check(threshold+' full pose reaches both soles and palm',ready.length>0&&soleGap<2e-5&&handGap<1e-8&&ready.every(f=>f.feet.every(x=>x.slideContact)&&f.slide.hand.touching));
  check(threshold+' contacts slide instead of remaining pinned in world',R.length(R.sub(ready.at(-1).feet[0].slideContact.point,ready[0].feet[0].slideContact.point))>1);
  check(threshold+' skeleton lengths and shoe volumes preserved',boneError<1e-10&&penetration<1e-5);
  check(threshold+' transition has no added hinge flip',kneeStep<15);
  check(threshold+' live recurrent replay matches physics',replayError<1e-8);
  cases.push({threshold,startFrame:start/2,entryVelocity:entry.surface.velocity,endVelocity:end.surface.velocity,nnSteps:model.coupling.steps,velocityError,positionError,boneError,replayError,soleGap,handGap,penetration,kneeStep,metrics:model.metrics});
 }
 check('Absolute velocity triggers ascent and descent',cases[0].entryVelocity[1]>0&&cases[1].entryVelocity[1]<0);
 fs.writeFileSync('snapshots/slide-verification.json',JSON.stringify({passed:true,checks,cases},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,cases}));
})().catch(e=>{console.error(e);process.exitCode=1});
