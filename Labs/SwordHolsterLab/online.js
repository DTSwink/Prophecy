/* Causal 60 Hz D/S: mirror the native rolling planner, never query future gait.
 * The worker records its output for smooth playback; that recording is not an
 * input to planning. Only authored profiles/targets may be evaluated ahead. */
(function(root){
'use strict';
const dep=(file,name)=>typeof module!=='undefined'?require('./'+file+'.js'):root[name];
const R=dep('recovery','Recovery'),FK=dep('armfk','ArmFK'),Body=dep('bodyreach','BodyReach');
const Tip=dep('tipalign','HolsterTipAlign');
const Pole=dep('elbowpole','ElbowPole'),Head=dep('headlook','HeadLook'),Return=dep('fkreturn','FKReturn'),Curve=dep('retime','Retime');
const {add,sub,mul,dot,length:len,unit,qm,qinv,rotate,qslerp,qlog,qexp,fromTo}=R;
const clamp=x=>Math.max(0,Math.min(1,x)),copy=t=>({p:[...t.p],q:[...t.q],s:[...(t.s||[1,1,1])]});
function fullSlerp(a,b,t){
 const d=Math.max(-1,Math.min(1,dot(a,b))),theta=Math.acos(d),s=Math.sin(theta);
 return Math.abs(s)<1e-8?[...a]:unit(a.map((v,k)=>(v*Math.sin((1-t)*theta)+b[k]*Math.sin(t*theta))/s));
}
function prepare(H,data,setup,input,motionOffset=0,reference=null){
 const o=H.sanitize(input),names=data.names,parents=data.parents,arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>names.indexOf(n)),pelvis=names.indexOf('pelvis');
 const action=o.sheathe?'sheathe':'draw',profile=o[action+'Return'],reachCurve=Curve.prepare(o[action+'Curve']),slideCurve=Curve.prepare(o[action+'SlideCurve']);
 const retained=1-o.shrinkPercent/100,tip=H.bladeTip(setup);
 let slideLength=setup.bladeLength*retained,slideTicks=Math.max(1,Math.ceil(slideLength/o.slidingSpeed*60));
 const local=copy(setup.holster);local.p=add(local.p,[o.holsterX,o.holsterY,o.holsterZ]);
 local.q=unit(qm(qm(qm(qexp([0,0,o.holsterYaw*Math.PI/180]),qexp([0,-o.holsterPitch*Math.PI/180,0])),qexp([-o.holsterRoll*Math.PI/180,0,0])),local.q));
 const neutral=H.motion(data,'idle',0),holsterReturnTicks=Math.ceil(o.holsterReturnDuration*60-1e-5);
 const model={o,motionOffset,names,parents,arm,pelvis,setup,data,tip,bladeLength:setup.bladeLength,holsterLocal:local,holsterReference:null,frames:[],sourceFrames:[],sourceLocals:[],headTrack:[],headContext:Head.make(data),completionTick:null,playbackDuration:o.duration,plan:null,online:!reference,tickPlayback:true};
 model.holsterPivot=H.holsterPivot(setup,o.holsterPivotPercent).map((v,i)=>v*local.s[i]);
 model.gripBranch=names.map((_,j)=>{for(let k=j;k>=0;k=parents[k])if(names[k]==='clavicle_r')return true;return false;});
 let ctx,entry,desired,source,destination,filtered,lastRefit=0,reachTicks=1,slideStart=null,slideEntry=null,dock=null,slideBody=null;
 let guideA,guideB,guideTickA=0,guideTickB=0,heldArm,basis,poleAngle=0,poleSpeed=0,swordDown=null;
 let beforeBase=null,beforePose=null,headState=null,lookOutTick=Infinity,bodyElapsed=0,entrySeeds=null;
 const entryLocal=pose=>R.localize(pose.map(p=>p.p),pose.map(p=>p.q),parents);
 // Keep arm lengths captured at admission, like native Authored.Local.
 function applyArm(base,locals){
  const out=FK.apply(base,arm,parents,locals);
  for(let k=1;k<3;k++){const j=arm[k],p=parents[j];out[j]={...out[j],p:add(out[p].p,rotate(out[p].q,mul(unit(locals[k].p),len(ctx.entryLocal.p[j]))))};}
  return out;
 }
 function endpoint(base,body,goal,seed){const pose=applyArm(Body.apply(ctx,base,body),seed);H.solve(pose,arm,goal);model.plan.endpointSolves++;return FK.capture(pose,arm,parents);}
 function transplant(body,donor){const a=entryLocal(body),b=entryLocal(donor),fk=R.fk({q:a.q.map((q,j)=>model.gripBranch[j]?b.q[j]:q),p:a.p.map((p,j)=>model.gripBranch[j]?b.p[j]:p)},parents);return body.map((p,j)=>model.gripBranch[j]?{...p,p:fk.points[j],q:fk.q[j]}:p);}
 function applyPole(pose,insertion,sliding,advance=true){
  let reference=ctx.top;
  if(sliding&&o.swordRelativeSlidePole){
   const swordQ=unit(qm(pose[arm[2]].q,setup.grip.q));
   if(!swordDown){basis=Pole.frame(pose,arm,ctx.top,basis);const q=qm(qinv(swordQ),pose[ctx.top].q);basis={d:rotate(q,basis.d),zero:rotate(q,basis.zero)};swordDown=basis.zero;}
   reference={q:swordQ,down:swordDown};
  }
  basis=Pole.frame(pose,arm,reference,basis);
  if(advance)poleAngle=Pole.advance(poleAngle,Pole.target(o.bodyTargets,sliding?insertion:o.sheathe?0:1),sliding?o.maxElbowPoleAngularSpeed:poleSpeed,1/60);
  return Pole.apply(pose,arm,reference,poleAngle,basis);
 }
 function makeReturn(tick,pose,base,handInertia=false){return {...Return.prepare({names,parents,last:pose,previous:beforePose||pose,base,previousBase:beforeBase||base,dt:1/60,profile,handInertia}),start:tick/60};}
 for(let tick=0;tick<=Math.ceil(o.duration*60);tick++){
  // These are the only time-varying input reads. Nothing below samples tick+1.
  const base=H.motion(data,o.motion,motionOffset+tick/60,o.gazeYaw),ungazed=H.motion(data,o.motion,motionOffset+tick/60,0);
  const holster=H.compose(local,base[pelvis]);
  if(model.holsterReference){
   const afterRelease=slideStart===null?0:Math.max(0,tick-slideStart-slideTicks);
   const weight=o.holsterRotationStabilization*(afterRelease>0?(holsterReturnTicks>0?1-clamp(afterRelease/holsterReturnTicks):0):1);
   if(weight>0){
    const offset=rotate(holster.q,model.holsterPivot);
    holster.q=qslerp(holster.q,model.holsterReference,weight);
    holster.p=add(holster.p,sub(offset,rotate(holster.q,model.holsterPivot)));
   }
  }
  const full=H.seatedSword(setup,holster),mouth=H.point(full,setup.baseBladeLocal),seat=H.seatHandAtScale(setup,full,retained);
  const goalAt=(progress,time=progress)=>o.sheathe?slideEntry?H.sheathSlideGoal(setup,holster,slideEntry.scale+(retained-slideEntry.scale)*(o.slideRotationCorrection>0?clamp(progress/o.slideRotationCorrection):progress>0?1:0),tip,slideEntry,progress,o.slideRotationCorrection,time):H.handForTip(setup,retained,tip,mouth,full.q):{...seat,p:sub(seat.p,mul(rotate(full.q,[0,0,1]),slideLength*progress))};
  let pose=base,body=null,progress=0,insertion=o.sheathe?0:1,scale=o.sheathe?1:retained,phase=o.sheathe?'Held':'Holstered',goal=goalAt(0),returnActive=false;
  if(tick===o.startTick){
   ctx=Body.make(data,neutral,base,o.pelvisRotationCompensation);model.bodyContext=ctx;entry=ctx.entryBody;desired=Body.target(ctx,o.bodyTargets,o.sheathe?0:1);source=FK.capture(base,arm,parents);
   model.plan={startTick:tick,arrives:false,endpointSolves:0};
   const bodyTicks=Math.ceil(Body.remaining(entry,desired)/o.maxSpineClavicleAngularSpeed*60);
   for(let pass=0;!reference&&pass<16;pass++){
    const body=[0,4,8].flatMap(k=>{const a=entry.slice(k,k+4),b=desired.slice(k,k+4),d=H.angle(a,b);return qslerp(a,b,d>0?Math.min(1,o.maxSpineClavicleAngularSpeed*reachTicks/60/d):1);});
    destination=endpoint(base,body,goal,source);const required=Math.max(bodyTicks,Math.ceil(FK.duration(source,destination,o.maxReachSpeed,o.maxReachRotationSpeed)*60));
    if(required<=reachTicks)break;reachTicks=required;
   }
   if(reference)reachTicks=reference.plan.reachEndTick-tick;
   destination=reference?reference.plan.reachDestination:endpoint(base,desired,goal,source);destination=destination.map((v,k)=>({...v,q:dot(source[k].q,v.q)<0?mul(v.q,-1):v.q}));filtered=destination;
   Object.assign(model.plan,{reachEndTick:tick+reachTicks,endTick:tick+reachTicks,slideEnd:tick+reachTicks+slideTicks});
   basis=Pole.frame(base,arm,ctx.top);poleAngle=Pole.measure(base,arm,ctx.top,basis);poleSpeed=Math.min(o.maxElbowPoleAngularSpeed,Math.abs(Pole.wrap(Pole.target(o.bodyTargets,o.sheathe?0:1)-poleAngle))*60/reachTicks);
   // Native entry inertia subtracts the first procedural velocity (body, arm
   // and pole). Extrapolate a tiny sample from observed velocity rather than
   // reading that time in the recording. It is a prediction, not future input.
   if(!reference&&o.entryInertia>0&&o.entryInertiaDuration>0){
    const dt=1e-4,prior=beforeBase||base;
    const predicted=sign=>base.map((v,j)=>({...v,p:add(v.p,mul(sub(v.p,prior[j].p),sign*dt*60)),q:unit(qm(v.q,qexp(mul(qlog(qm(qinv(prior[j].q),v.q)),sign*dt*60))))}));
    const fraction=Curve.sample(reachCurve,dt*60/reachTicks);
    let nextPose=applyArm(Body.apply(ctx,predicted(1),Body.blend(entry,desired,fraction)),FK.blend(source,destination,fraction));
    const nextBasis=Pole.frame(nextPose,arm,ctx.top,basis),nextAngle=Pole.advance(poleAngle,Pole.target(o.bodyTargets,o.sheathe?0:1),poleSpeed,dt);
    nextPose=Pole.apply(nextPose,arm,ctx.top,nextAngle,nextBasis);
    const prev=entryLocal(predicted(-1)),next=entryLocal(nextPose);
    entrySeeds=ctx.inertiaBones.map(j=>({j,q:mul(sub(qlog(qm(qinv(prev.q[j]),ctx.entryLocal.q[j])),qlog(qm(qinv(ctx.entryLocal.q[j]),next.q[j]))),o.entryInertia/dt),p:mul(sub(qlog(fromTo(prev.p[j],ctx.entryLocal.p[j])),qlog(fromTo(ctx.entryLocal.p[j],next.p[j]))),o.entryInertia/dt)}));
   }
  }
  if(ctx&&tick>=o.startTick){
   const elapsed=tick-o.startTick,reachFraction=Curve.sample(reachCurve,elapsed/reachTicks);progress=reachFraction;
   const sliding=slideStart!==null,slideTime=sliding?clamp((tick-slideStart)/slideTicks):0,slideProgress=sliding?Curve.sample(slideCurve,slideTime):0;
   insertion=sliding?(o.sheathe?slideEntry.insertion+(1-slideEntry.insertion)*slideProgress:1-slideProgress):(o.sheathe?0:1);
   const bodyState=sliding?(slideBody?Body.blend(slideBody,Body.target(ctx,o.bodyTargets,1),slideProgress):Body.target(ctx,o.bodyTargets,insertion)):Body.blend(entry,desired,reachFraction);
   pose=Body.apply(ctx,base,bodyState);body={entry,applied:bodyState,desired,requiredDegrees:Body.remaining(entry,desired),remainingDegrees:Body.remaining(bodyState,desired),spineArrivalTick:o.startTick+reachTicks,clavicleArrivalTick:o.startTick+reachTicks};
   phase=sliding?'Slide':'Reach';goal=goalAt(slideProgress,slideTime);
   if(!sliding&&!dock&&!reference){
    if(elapsed>0&&(elapsed%4===0||elapsed>=reachTicks)){
     filtered=FK.blend(filtered,destination,clamp((elapsed-lastRefit)/4));
     const fit=endpoint(base,desired,goal,source);destination=fit.map((v,k)=>({...v,q:dot(destination[k].q,v.q)<0?mul(v.q,-1):v.q}));lastRefit=elapsed;
    }
    const target=FK.blend(filtered,destination,clamp((elapsed-lastRefit+1)/4));
    pose=applyArm(pose,source.map((v,k)=>({q:fullSlerp(v.q,target[k].q,progress),p:R.offsetBlend(v.p,target[k].p,progress)})));heldArm=FK.capture(pose,arm,parents);
   }else if(sliding&&tick<=slideStart+slideTicks&&!model.fkReturn){
    const at=tick-slideStart;
    while(at>guideTickB){
     guideTickA=guideTickB;guideA=guideB;
     const spacing=Math.max(1,Math.min(4,2*slideTicks/Math.max(slideLength,1)));
     guideTickB=Math.min(slideTicks,Math.max(at,(Math.floor(guideTickA/spacing+1e-8)+1)*spacing));
     const cut=slideTicks*o.slideRotationCorrection;if(o.sheathe&&cut>guideTickA&&cut<guideTickB)guideTickB=cut;
     const u=guideTickB/slideTicks,p=Curve.sample(slideCurve,u);
     guideB=endpoint(base,slideBody?Body.blend(slideBody,Body.target(ctx,o.bodyTargets,1),p):Body.target(ctx,o.bodyTargets,o.sheathe?p:1-p),goalAt(p,u),guideA);
    }
    pose=applyArm(pose,FK.blend(guideA,guideB,clamp((at-guideTickA)/Math.max(1e-12,guideTickB-guideTickA))));
   }
   if(!model.fkReturn&&(!reference||sliding)&&(!dock||sliding)){
    pose=applyPole(pose,insertion,sliding,elapsed>0);
    const duration=Math.min(o.entryInertiaDuration,reachTicks/60),time=elapsed/60;
    if(!sliding&&entrySeeds&&time>0&&time<duration){
     const localPose=entryLocal(pose),momentum=time*Math.pow(1-time/duration,3);
     for(const v of entrySeeds){localPose.q[v.j]=unit(qm(localPose.q[v.j],qexp(mul(v.q,momentum))));localPose.p[v.j]=rotate(qexp(mul(v.p,momentum)),localPose.p[v.j]);}
     const fk=R.fk(localPose,parents);pose=pose.map((p,j)=>ctx.affected.includes(j)?{...p,p:fk.points[j],q:fk.q[j]}:p);
    }
   }
   scale=o.sheathe?sliding?slideEntry.scale+(retained-slideEntry.scale)*(o.slideRotationCorrection>0?clamp(slideProgress/o.slideRotationCorrection):slideProgress>0?1:0):H.reachScale(o,tick):retained;
   if(reference&&!dock&&!sliding){
    const f=H.sampleBody(reference,tick/60);
    pose=f.pose.map(copy);body=f.body;scale=f.scale;progress=f.progress;goal=f.goal;
    heldArm=FK.capture(pose,arm,parents);
    basis=Pole.frame(pose,arm,ctx.top,basis);poleAngle=Pole.measure(pose,arm,ctx.top,basis);
   }
   if(o.sheathe&&o.leewayPhase&&!sliding){
    if(!dock){
     const sword=H.compose(H.scaledGrip(setup,scale),pose[arm[2]]);
     if(H.angle(sword.q,full.q)<=o.sheatheRotationTolerance+1e-5){
      dock=Tip.begin(H,setup,tip,sword,holster,pose[arm[2]],scale,tick,o);model.tipAlign=dock;
      if(o.holsterRotationStabilization>0){model.holsterReference=[...holster.q];model.holsterGripTick=tick;}
      heldArm=FK.capture(pose,arm,parents);
      model.plan.attachTick=tick;model.plan.endTick=tick+dock.ticks;model.plan.slideEnd=model.plan.endTick+slideTicks;
     }
    }
    if(dock){
     phase='Align tip';scale=dock.scale;
     const aligned=Tip.sample(H,setup,tip,dock,holster,tick);goal=aligned.goal;
     if(tick>dock.tick){
      pose=applyArm(pose,heldArm);const seed=pose.map(copy);
      H.solve(pose,arm,goal);model.plan.endpointSolves++;pose=applyPole(pose,0,false);
      // Swivelling a nearly straight elbow must not inject an axial half-turn.
      // Carry each segment's existing roll through its actual direction change.
      for(let k=0;k<2;k++){const j=arm[k],child=arm[k+1];pose[j]={...pose[j],q:unit(qm(fromTo(sub(seed[child].p,seed[j].p),sub(pose[child].p,pose[j].p)),seed[j].q))};}
      heldArm=FK.capture(pose,arm,parents);
     }
    }
   }
   if(!sliding){
    const sword=H.compose(H.scaledGrip(setup,scale),dock?goal:pose[arm[2]]);
    const alignedTip=dock?add(holster.p,rotate(holster.q,dock.tipLocal)):mouth;
    const sheathArrived=o.leewayPhase
     ?!!dock&&tick>=dock.tick+dock.ticks&&len(sub(H.point(sword,tip),alignedTip))<=1e-4
     :len(sub(H.point(sword,tip),mouth))<=o.sheatheTipTolerance&&H.angle(sword.q,full.q)<=o.sheatheRotationTolerance+1e-5;
    const arrived=o.sheathe?sheathArrived:elapsed>=reachTicks&&len(sub(pose[arm[2]].p,goal.p))<=2&&H.angle(pose[arm[2]].q,goal.q)<=5;
    if(arrived){
     slideStart=tick;model.plan.arrives=true;model.plan.endTick=tick;
     if(o.sheathe){
      insertion=dock?.insertion??0;
      if(!dock){model.plan.attachTick=tick;heldArm=FK.capture(pose,arm,parents);}
      const seated=H.compose(H.scaledGrip(setup,scale),H.seatHandAtScale(setup,full,scale));
      const startTip=add(mouth,mul(sub(H.point(seated,tip),mouth),insertion));
      slideEntry={tick,scale,insertion,q:unit(qm(qinv(full.q),sword.q)),tipError:rotate(qinv(full.q),sub(H.point(sword,tip),startTip))};slideBody=[...body.applied];
      slideLength=setup.bladeLength*retained*Math.abs(1-insertion);slideTicks=Math.max(1,Math.ceil(slideLength/o.slidingSpeed*60));
     }
     model.plan.slideEnd=tick+slideTicks;
     if(o.holsterRotationStabilization>0){
      if(!model.holsterReference){model.holsterReference=[...holster.q];model.holsterGripTick=tick;}
      model.holsterReturnEndTick=tick+slideTicks+Math.max(1,holsterReturnTicks);
     }
     model.sheathEntry=slideEntry;guideA=guideB=heldArm;applyPole(pose,insertion,true,false);phase='Slide';goal=goalAt(0);
    }
   }
   if(sliding){
    const release=slideStart+slideTicks,holding=tick<=release;
    if(!model.fkReturn&&(o.sheathe?insertion:slideProgress)>=profile.startFraction-1e-8&&profile.enabled){model.fkReturn=makeReturn(tick,pose,base);heldArm=FK.capture(pose,arm,parents);}
    const ret=model.fkReturn;
    if(ret&&tick/60>ret.start){
     if(holding&&ret.start<release/60){
      const donor=pose,at=time=>transplant(Return.sample(ret,base,time),donor),reachable=p=>len(sub(p[arm[0]].p,goal.p))<=len(sub(p[arm[1]].p,p[arm[0]].p))+len(sub(p[arm[2]].p,p[arm[1]].p))-.001;
      let next=bodyElapsed+1/60;pose=at(next);
      if(!reachable(pose)){let lo=bodyElapsed,hi=next;pose=at(lo);if(reachable(pose))for(let i=0;i<8;i++){const mid=(lo+hi)/2;if(reachable(at(mid)))lo=mid;else hi=mid;}next=lo;pose=at(next);}
      bodyElapsed=next;pose=applyArm(pose,heldArm);H.solve(pose,arm,goal);pose=applyPole(pose,insertion,true);heldArm=FK.capture(pose,arm,parents);
     }else{bodyElapsed+=1/60;pose=Return.sample(ret,base,bodyElapsed);}
    }
    if(ret&&tick===release&&ret.start<release/60){model.armReturn=makeReturn(tick,pose,base,!o.sheathe);ret.gripDelay=Math.max(0,release/60-ret.start-bodyElapsed);}
    if(model.armReturn&&tick>release)pose=transplant(pose,Return.sample(model.armReturn,base,(tick-release)/60));
    returnActive=!!ret&&(bodyElapsed<ret.timing.duration-1e-12||!!model.armReturn&&(tick-release)/60<model.armReturn.timing.duration-1e-12);
    if(tick>=release){const grow=o.unshrinkDuration<=0?1:clamp((tick-release)/60/o.unshrinkDuration);if(!o.sheathe)scale=retained+(1-retained)*grow;phase=returnActive?'FK return':o.sheathe?'Holstered':grow>=1?'Held':'Unshrink';}
    if((o.sheathe?insertion:slideProgress)>=(o.sheathe?o.sheatheHeadLookOutThreshold:o.drawHeadLookOutThreshold)-1e-8&&lookOutTick===Infinity)lookOutTick=tick;
   }
  }
  const held=phase==='Held'||phase==='Unshrink'||phase==='FK return'&&!o.sheathe||phase==='Reach'&&o.sheathe;
  const sword=held?H.compose(H.scaledGrip(setup,scale),pose[arm[2]]):phase==='Align tip'||phase==='Slide'?H.compose(H.scaledGrip(setup,scale),goal):H.compose(H.scaledGrip(setup,retained),seat);
  const headTarget=o.sheathe?add(H.point(sword,tip),mul(sub(mouth,H.point(sword,tip)),o.sheatheHeadTargetAlpha)):mouth;
  let look=Head.step(model.headContext,pose,ungazed,headTarget,headState,{tick,startTick:o.startTick,lookOutTick,maxLookIn:H.headSpeed(o,false,o.gazeYaw),maxLookOut:H.headSpeed(o,true,o.gazeYaw),lookAtAlpha:o.headLookAtAlpha,maxDownAngle:o.headMaxDownAngle,lookInSpeedAlpha:o.headLookInSpeedAlpha,handArrivalTick:dock?dock.tick+dock.ticks:o.startTick+reachTicks,lookInExponent:o.headLookInExponent,lookOutExponent:o.headLookOutExponent,neckBase:ungazed,gazeNeckBase:base,lookOutQ:tick>=lookOutTick?base[model.headContext.head].q:null});
  if(reference&&(o.sheathe&&o.leewayPhase?(!dock||tick<=dock.tick):(slideStart===null||tick===slideStart))&&reference.frames[tick]){
   const f=reference.frames[tick],h=reference.headTrack[tick];
   look={pose:f.pose.map(copy),info:f.headLook,state:{...h,referenceQ:headState?.referenceQ||ungazed[model.headContext.head].q}};
  }
  headState=look.state;
  const handError=len(sub(pose[arm[2]].p,goal.p)),active=['Reach','Align tip','Slide','Unshrink'].includes(phase)||returnActive||!look.info.done||tick<(model.holsterReturnEndTick??0);
  const armLength=len(sub(pose[arm[1]].p,pose[arm[0]].p))+len(sub(pose[arm[2]].p,pose[arm[1]].p)),shoulderTarget=len(sub(goal.p,pose[arm[0]].p));
  const frame={tick,pose:look.pose,body,holster,sword,goal,commandedHand:ctx?copy(pose[arm[2]]):null,phase,scale,insertion,progress,active,handError,blocked:phase==='Reach'&&progress>=1&&handError>2,metrics:{armLength,shoulderTarget,unreachable:Math.max(0,shoulderTarget-armLength),handError},headLook:look.info,elbowPoleAngle:poleAngle,attached:!!dock||o.sheathe&&slideStart!==null,tipAlignProgress:dock?clamp((tick-dock.tick)/dock.ticks):null};
  if(model.fkReturn)frame.fkReturn={elapsed:bodyElapsed,duration:model.fkReturn.timing.duration,active:returnActive,gripping:slideStart!==null&&tick<slideStart+slideTicks,armStart:model.armReturn?.start};
  model.frames.push(frame);model.sourceLocals.push(entryLocal(frame.pose));model.headTrack.push({q:headState.q,info:look.info});beforeBase=base;beforePose=look.pose;
  if(tick>=o.startTick&&!active){model.completionTick=tick;model.playbackDuration=tick/60;break;}
 }
 model.sourceFrames=model.frames;
 if(!model.bodyContext)model.bodyContext=Body.make(data,neutral,model.frames[0].pose,o.pelvisRotationCompensation);
 const end=model.plan?.endTick??o.duration*60,reachEnd=model.plan?.attachTick??end;
 model.retimeSegments={reach:{start:o.startTick/60,end:reachEnd/60,curve:reachCurve},align:{start:reachEnd/60,end:end/60},slide:{start:end/60,end:(model.plan?.slideEnd??end)/60,curve:slideCurve}};
 return model;
}
function sample(model,t){
 const x=Math.max(0,Math.min(model.frames.length-1,t*60)),i=Math.floor(x),u=x-i,a=model.frames[i],b=model.frames[Math.min(i+1,model.frames.length-1)];if(u<1e-10)return a;
 const la=model.sourceLocals[i],lb=model.sourceLocals[Math.min(i+1,model.frames.length-1)],fk=R.fk({q:la.q.map((q,j)=>qslerp(q,lb.q[j],u)),p:la.p.map((p,j)=>R.offsetBlend(p,lb.p[j],u))},model.parents);
 const blend=(a,b)=>({p:add(a.p,mul(sub(b.p,a.p),u)),q:qslerp(a.q,b.q,u),s:(a.s||[1,1,1]).map((v,k)=>v+((b.s||[1,1,1])[k]-v)*u)});
 const holster=blend(a.holster,b.holster);let sword=blend(a.sword,b.sword),goal=blend(a.goal,b.goal);
 // Keep the pivot on the displayed pelvis also between recorded ticks.
 const pivot=model.holsterPivot,neutralQ=unit(qm(fk.q[model.pelvis],model.holsterLocal.q));
 const neutralP=add(fk.points[model.pelvis],rotate(fk.q[model.pelvis],model.holsterLocal.p));
 const oldP=holster.p;holster.p=add(neutralP,sub(rotate(neutralQ,pivot),rotate(holster.q,pivot)));
 if(!model.o.sheathe&&x<=(model.plan?.slideEnd??Infinity)){
  const delta=sub(holster.p,oldP);sword={...sword,p:add(sword.p,delta)};goal={...goal,p:add(goal.p,delta)};
 }
 if(model.o.sheathe&&a.attached){
  const carry=(v,old)=>{const local=Tip.relative(v,old);return {...local,p:add(holster.p,rotate(holster.q,local.p.map((x,i)=>x*holster.s[i]))),q:unit(qm(holster.q,local.q)),s:local.s.map((x,i)=>x*holster.s[i])};};
  if(a.phase==='Align tip'){
   const H=typeof module!=='undefined'?require('./holster.js'):root.Holster;
   ({sword,goal}=Tip.sample(H,model.setup,model.tip,model.tipAlign,holster,x));
  }else{sword=blend(carry(a.sword,a.holster),carry(b.sword,b.holster));goal=blend(carry(a.goal,a.holster),carry(b.goal,b.holster));}
 }
 return {...a,pose:a.pose.map((p,j)=>({...p,p:fk.points[j],q:fk.q[j]})),sword,holster,goal,insertion:a.insertion+(b.insertion-a.insertion)*u,scale:a.scale+(b.scale-a.scale)*u,progress:a.progress+(b.progress-a.progress)*u};
}
const api={prepare,sample};if(typeof module!=='undefined')module.exports=api;else root.HolsterOnline=api;
})(globalThis);
