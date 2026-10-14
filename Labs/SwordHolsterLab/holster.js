/* Deterministic 60-tick D/S pose model. UE coordinates and centimetres internally. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const Online=typeof module!=='undefined'?require('./online.js'):root.HolsterOnline;
const Retime=typeof module!=='undefined'?require('./retime.js'):root.Retime;
const FK=typeof module!=='undefined'?require('./armfk.js'):root.ArmFK;
const Return=typeof module!=='undefined'?require('./fkreturn.js'):root.FKReturn;
const Head=typeof module!=='undefined'?require('./headlook.js'):root.HeadLook;
const Pole=typeof module!=='undefined'?require('./elbowpole.js'):root.ElbowPole;
const Body=typeof module!=='undefined'?require('./bodyreach.js'):root.BodyReach;
const {add,sub,mul,dot,cross,length:len,unit,qm,qinv,rotate,qslerp,fromTo,toAxes}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),I=[0,0,0,1];
const had=(a,b)=>a.map((x,i)=>x*b[i]);
const copy=t=>({p:[...t.p],q:[...t.q],s:[...(t.s||[1,1,1])]});
const compose=(a,b)=>({p:add(b.p,rotate(b.q,had(b.s||[1,1,1],a.p))),q:unit(qm(b.q,a.q)),s:had(a.s||[1,1,1],b.s||[1,1,1])});
const angle=(a,b)=>2*Math.acos(clamp(Math.abs(dot(a,b)),-1,1))*180/Math.PI;
const defaults={noCheat:false,leewayPhase:true,holsterRotationStabilization:0,holsterReturnDuration:.25,holsterPivotPercent:50,pelvisRotationCompensation:1,entryInertia:1,entryInertiaDuration:.2,maxElbowPoleAngularSpeed:180,swordRelativeSlidePole:false,bodyTargets:Body.sanitize(),gazeYaw:0,sheatheRotationTolerance:15,sheatheTipTolerance:2,slideRotationCorrection:.1,motion:'idle',sheathe:true,startTick:25,maxReachSpeed:100,maxReachRotationSpeed:180,maxAttachedSpeed:100,maxAttachedRotationSpeed:180,slidingSpeed:60,shrinkPercent:35,shrinkDuration:.25,unshrinkDuration:.5,holsterX:0,holsterY:0,holsterZ:0,holsterPitch:0,holsterYaw:0,holsterRoll:0,duration:8,spineClavicleAngleLimit:45,maxSpineClavicleAngularSpeed:90,drawReturn:{...Return.defaults(),startFraction:.7},sheatheReturn:Return.defaults(),headLookAtAlpha:1,headMaxDownAngle:70,headLookInSpeedAlpha:1,sheatheHeadTargetAlpha:1,headLookInExponent:1,headLookOutExponent:1,maxHeadLookInVelocity:180,maxHeadLookOutVelocity:180,maxHeadLookInVelocityAtMaxGaze:180,maxHeadLookOutVelocityAtMaxGaze:180,drawHeadLookOutThreshold:.3,sheatheHeadLookOutThreshold:.5,drawCurve:Retime.linear(),sheatheCurve:Retime.linear(),drawSlideCurve:Retime.linear(),sheatheSlideCurve:Retime.linear()};
function sanitize(input={}){const o={...defaults,...input};for(const [to,from] of [['maxAttachedSpeed','maxReachSpeed'],['maxAttachedRotationSpeed','maxReachRotationSpeed']])if(input[to]===undefined)o[to]=input.sheatheBody?.[from]??input[from]??defaults[to];if(input.shrinkDuration===undefined&&input.shrinkSpeed!==undefined)o.shrinkDuration=Number(o.shrinkPercent)/Math.max(.01,Number(input.shrinkSpeed)||100);delete o.shrinkSpeed;delete o.drawReachIK;o.noCheat=input.noCheat===true;o.leewayPhase=input.leewayPhase!==false;o.bodyTargets=Body.sanitize(input.bodyTargets);for(const k of ['maxHeadLookInVelocity','maxHeadLookOutVelocity'])if(input[k+'AtMaxGaze']===undefined)o[k+'AtMaxGaze']=o[k];for(const k of Object.keys(defaults))if(typeof defaults[k]==='number')o[k]=Number.isFinite(Number(o[k]))?Number(o[k]):defaults[k];o.holsterRotationStabilization=clamp(o.holsterRotationStabilization,0,1);o.holsterReturnDuration=clamp(o.holsterReturnDuration,0,10);o.holsterPivotPercent=clamp(o.holsterPivotPercent,0,100);o.pelvisRotationCompensation=clamp(o.pelvisRotationCompensation,0,1);o.entryInertia=clamp(o.entryInertia,0,1);o.entryInertiaDuration=clamp(o.entryInertiaDuration,0,1);o.maxElbowPoleAngularSpeed=clamp(o.maxElbowPoleAngularSpeed,0,10000);o.gazeYaw=clamp(o.gazeYaw,-170,170);o.sheatheRotationTolerance=clamp(o.sheatheRotationTolerance,0,90);o.sheatheTipTolerance=clamp(o.sheatheTipTolerance,0,100);o.slideRotationCorrection=clamp(o.slideRotationCorrection,0,1);o.startTick=Math.round(clamp(o.startTick,0,3600));o.duration=clamp(o.duration,1,60);o.shrinkPercent=clamp(o.shrinkPercent,0,99.9);o.shrinkDuration=clamp(o.shrinkDuration,.01,60);o.unshrinkDuration=clamp(o.unshrinkDuration,0,10);for(const k of ['maxReachSpeed','maxReachRotationSpeed','maxAttachedSpeed','maxAttachedRotationSpeed','slidingSpeed'])o[k]=clamp(o[k],.01,10000);o.spineClavicleAngleLimit=clamp(o.spineClavicleAngleLimit,0,90);o.maxSpineClavicleAngularSpeed=clamp(o.maxSpineClavicleAngularSpeed,.01,10000);o.drawReturn=Return.sanitize(o.drawReturn);o.sheatheReturn=Return.sanitize(o.sheatheReturn);delete o.headCorrectionAlpha;for(const k of ['headLookInExponent','headLookOutExponent'])o[k]=clamp(o[k],1,8);o.headLookAtAlpha=clamp(o.headLookAtAlpha,0,1);o.headMaxDownAngle=clamp(o.headMaxDownAngle,0,90);o.headLookInSpeedAlpha=clamp(o.headLookInSpeedAlpha,0,1);o.sheatheHeadTargetAlpha=clamp(o.sheatheHeadTargetAlpha,0,1);for(const k of ['maxHeadLookInVelocity','maxHeadLookOutVelocity','maxHeadLookInVelocityAtMaxGaze','maxHeadLookOutVelocityAtMaxGaze'])o[k]=clamp(o[k],.01,10000);for(const k of ['drawHeadLookOutThreshold','sheatheHeadLookOutThreshold'])o[k]=clamp(o[k],0,1);o.motion=['walk','run'].includes(o.motion)||/^problem_\d+$/.test(o.motion)?o.motion:'idle';o.sheathe=!!o.sheathe;o.swordRelativeSlidePole=o.swordRelativeSlidePole===true;o.drawCurve=Retime.sanitize(o.drawCurve);o.sheatheCurve=Retime.sanitize(o.sheatheCurve);o.drawSlideCurve=Retime.sanitize(o.drawSlideCurve);o.sheatheSlideCurve=Retime.sanitize(o.sheatheSlideCurve);return o;}
function euler(p,y,r){return qm(qm(R.qexp([0,0,y*Math.PI/180]),R.qexp([0,-p*Math.PI/180,0])),R.qexp([-r*Math.PI/180,0,0]));}
// Accepted training/viewer gaze yaw overlay: local-X subtree rotations with
// incremental 1..8 / 36 weights. Pelvis and lower body remain authored.
function gazePose(data,pose,degrees){
 if(!degrees)return pose;
 const out=pose.map(copy),chain=['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head'];
 for(let k=0;k<chain.length;k++){
  const j=data.names.indexOf(chain[k]),pivot=out[j].p;
  const q=R.qexp(mul(rotate(out[j].q,[1,0,0]),degrees*Math.PI/180*(k+1)/36));
  for(let n=0;n<out.length;n++){
   let descendant=false;for(let p=n;p>=0;p=data.parents[p])if(p===j){descendant=true;break;}
   if(!descendant)continue;
   if(n!==j)out[n].p=add(pivot,rotate(q,sub(out[n].p,pivot)));
   out[n].q=unit(qm(q,out[n].q));
  }
 }
 return out;
}
function motion(data,key,t,gaze=0){
 const clip=data.motions[key],duration=clip.duration,fps=clip.fps||data.fps,u=(clip.loop===false?clamp(t,0,duration):t%duration)*fps,i=Math.min(clip.frames.length-2,Math.floor(u)),v=(u-i)/Math.min(1,duration*fps-i);
 const frames=clip.frames,first=frames[0][0],last=frames.at(-1)[0],loops=Math.floor(t/duration),drift=mul(sub(last.slice(0,3),first.slice(0,3)),loops);
 const rootNow=add(frames[i][0].slice(0,3),mul(sub(frames[i+1][0].slice(0,3),frames[i][0].slice(0,3)),v));
 return gazePose(data,frames[i].map((a,j)=>({p:sub(add(a.slice(0,3),mul(sub(frames[i+1][j].slice(0,3),a.slice(0,3)),v)),[rootNow[0],rootNow[1],0]),q:qslerp(a.slice(3),frames[i+1][j].slice(3),v),s:[1,1,1]})),gaze);
}
// Axial pivot in mesh-local coordinates; changing it never edits neutral placement.
function holsterPivot(setup,percent){
 let lo=Infinity,hi=-Infinity;
 for(const section of setup.holsterMesh.sections)for(const v of section.vertices){lo=Math.min(lo,v[2]);hi=Math.max(hi,v[2]);}
 return [0,0,lo+(hi-lo)*percent/100];
}
function reachScale(o,tick){return 1-o.shrinkPercent/100*clamp((tick-o.startTick)/60/o.shrinkDuration,0,1);}
function scaledGrip(setup,scale){const g=copy(setup.grip);g.p=rotate(g.q,had(rotate(qinv(g.q),g.p),[1,1,scale]));g.s=had(setup.assetScale,[1,1,scale]);return g;}
function seatHandAtScale(setup,full,scale){
 // Keep the authored blade-base point seated while shortening about the grip.
 // Reusing the full-size hand transform would lift the shortened base off the mouth.
 const grip=scaledGrip(setup,scale),q=unit(qm(full.q,qinv(grip.q)));
 const seatedBase=add(full.p,rotate(full.q,had(full.s,setup.baseBladeLocal)));
 const swordOrigin=sub(seatedBase,rotate(full.q,had(grip.s,setup.baseBladeLocal)));
 return {p:sub(swordOrigin,rotate(q,grip.p)),q,s:[1,1,1]};
}
function bladeTip(setup){return setup.swordMesh.sections.flatMap(s=>s.vertices).reduce((a,b)=>a[2]>b[2]?a:b);}
const point=(t,p)=>add(t.p,rotate(t.q,had(t.s,p)));
function seatedSword(setup,holster){
 // Approach the hilt palm-in. Roll about the blade axis at the mouth, leaving
 // the exported reference, insertion line and ordinary hand grip untouched.
 const full=compose(setup.seated,holster),mouth=point(full,setup.baseBladeLocal);
 const q=unit(qm(full.q,[0,0,1,0]));
 return {...full,q,p:sub(mouth,rotate(q,had(full.s,setup.baseBladeLocal)))};
}
function handForTip(setup,scale,tip,position,swordRotation){
 const g=scaledGrip(setup,scale),q=unit(qm(swordRotation,qinv(g.q)));
 return {p:sub(sub(position,rotate(swordRotation,had(g.s,tip))),rotate(q,g.p)),q,s:[1,1,1]};
}
function slideCorrection(insertion,alpha){return alpha>0?clamp(insertion/alpha,0,1):insertion>0?1:0;}
function sheathScale(retained,entry,insertion,alpha){return entry.scale+(retained-entry.scale)*slideCorrection(insertion,alpha);}
function sheathSlideGoal(setup,holster,scale,tip,entry,insertion,alpha,rotationProgress=insertion){
 const full=seatedSword(setup,holster),mouth=point(full,setup.baseBladeLocal);
 const seat=compose(scaledGrip(setup,scale),seatHandAtScale(setup,full,scale));
 const correction=slideCorrection(insertion,alpha);
 const q=unit(qm(full.q,qslerp(entry.q,I,slideCorrection(rotationProgress,alpha))));
 const depth=(entry.insertion??0)+(1-(entry.insertion??0))*insertion;
 const position=add(add(mouth,mul(sub(point(seat,tip),mouth),depth)),mul(rotate(full.q,entry.tipError),1-correction));
 return handForTip(setup,scale,tip,position,q);
}
function solve(pose,idx,goal,poleHint=null){
 const [s,e,h]=idx,A=pose[s].p,B=pose[e].p,C=pose[h].p,L1=len(sub(B,A)),L2=len(sub(C,B));
 const delta=sub(goal.p,A),direction=len(delta)>1e-8?unit(delta):[1,0,0],distance=len(delta),D=clamp(distance,Math.abs(L1-L2)+.001,L1+L2-.001);
 let pole=poleHint?sub(poleHint,mul(direction,dot(poleHint,direction))):sub(sub(B,A),mul(direction,dot(sub(B,A),direction)));
 if(len(pole)<1e-7&&poleHint)pole=sub(sub(B,A),mul(direction,dot(sub(B,A),direction)));
 if(len(pole)<1e-7)pole=cross(direction,Math.abs(direction[2])<.9?[0,0,1]:[0,1,0]);pole=unit(pole);
 const along=(L1*L1+D*D-L2*L2)/(2*D),E=add(add(A,mul(direction,along)),mul(pole,Math.sqrt(Math.max(0,L1*L1-along*along)))),H=add(A,mul(direction,D));
 pose[s].q=unit(qm(fromTo(sub(B,A),sub(E,A)),pose[s].q));pose[e].q=unit(qm(fromTo(sub(C,B),sub(H,E)),pose[e].q));pose[e].p=E;pose[h].p=H;pose[h].q=[...goal.q];
 return {armLength:L1+L2,shoulderTarget:distance,unreachable:Math.max(0,distance-L1-L2),handError:len(sub(H,goal.p))};
}
function prepare(data,setup,input,motionOffset=0){
 if(input?.noCheat)return Return.prepareSwordPoint(Online.prepare(api,data,setup,input,motionOffset),compose,scaledGrip);
 const o=sanitize(input);
 // The original reach planner sees the neutral mount. Grip-relative holster
 // motion starts only after admission, in the shared current-tick continuation.
 const reference=prepareReference(data,setup,{...o,holsterRotationStabilization:0},motionOffset);
 return reference.plan&&(o.sheathe||o.holsterRotationStabilization>0)?Return.prepareSwordPoint(Online.prepare(api,data,setup,o,motionOffset,reference),compose,scaledGrip):reference;
}
function prepareReference(data,setup,input,motionOffset=0){
 const o=sanitize(input),N=data.names,arm=['upperarm_r','lowerarm_r','hand_r'].map(x=>N.indexOf(x)),pelvis=N.indexOf('pelvis');
 const bladeLength=setup.bladeLength,retained=1-o.shrinkPercent/100,lastTick=Math.ceil(o.duration*60),bodyContext=Body.make(data,motion(data,'idle',0),motion(data,o.motion,motionOffset+o.startTick/60,o.gazeYaw),o.pelvisRotationCompensation),tip=bladeTip(setup);
 const local=copy(setup.holster);local.p=add(local.p,[o.holsterX,o.holsterY,o.holsterZ]);local.q=unit(qm(euler(o.holsterPitch,o.holsterYaw,o.holsterRoll),local.q));
 const track=[],entryBody=bodyContext.entryBody;
 const bodyDesired=Body.target(bodyContext,o.bodyTargets,o.sheathe?0:1);let bodyState=[...entryBody],slideEntry=null;
 for(let tick=0;tick<=lastTick;tick++){
  const base=motion(data,o.motion,motionOffset+tick/60,o.gazeYaw),holster=compose(local,base[pelvis]),full=seatedSword(setup,holster);
  const seatHand=seatHandAtScale(setup,full,retained);
  const mouth=point(full,setup.baseBladeLocal);
  const goalAt=x=>{
   if(!o.sheathe)return {...copy(seatHand),p:sub(seatHand.p,mul(rotate(full.q,[0,0,1]),bladeLength*retained*(1-x)))};
   if(slideEntry&&tick>=slideEntry.tick)return sheathSlideGoal(setup,holster,sheathScale(retained,slideEntry,x,o.slideRotationCorrection),tip,slideEntry,x,o.slideRotationCorrection);
   return handForTip(setup,retained,tip,mouth,full.q);
  };
  let pose=base,body=null;
  if(tick>=o.startTick){
   const clearTarget=goalAt(0).p;
   if(tick>o.startTick)bodyState=Body.advance(bodyState,bodyDesired,o.maxSpineClavicleAngularSpeed);pose=Body.apply(bodyContext,base,bodyState);
   body={entry:[...entryBody],requiredDegrees:Body.remaining(entryBody,bodyDesired),applied:[...bodyState],desired:[...bodyDesired],remainingDegrees:Body.remaining(bodyState,bodyDesired),clearTarget,
    baseShoulderDistance:len(sub(base[arm[0]].p,clearTarget)),shoulderDistance:len(sub(pose[arm[0]].p,clearTarget))};
  }
  track.push({tick,base,pose,body,holster,full,mouth,seatHand,goalAt,slideLength:bladeLength*retained});
 }
 const frameAt=t=>track[clamp(Math.round(t),0,lastTick)];
 let plan=null;
 if(o.startTick<=lastTick){
  const args={arm,parents:data.parents,neutral:FK.capture(motion(data,'idle',0),arm,data.parents),frameAt,startTick:o.startTick,lastTick,o,solve,
   arrivalCheck:o.sheathe?(f,pose,progress)=>{const sword=compose(scaledGrip(setup,reachScale(o,f.tick)),pose[arm[2]]);return f.body.remainingDegrees<1e-5&&len(sub(point(sword,tip),f.mouth))<=(o.leewayPhase?2:o.sheatheTipTolerance)&&angle(sword.q,f.full.q)<=o.sheatheRotationTolerance+1e-5;}:null,
   beginSlide:o.sheathe?(f,pose,tick,progress)=>{const scale=reachScale(o,tick),sword=compose(scaledGrip(setup,scale),pose[arm[2]]);slideEntry={tick,scale,q:unit(qm(qinv(f.full.q),sword.q)),tipError:rotate(qinv(f.full.q),sub(point(sword,tip),f.mouth))};}:null};
  let totalSolves=0;
  const makePlan=options=>{slideEntry=null;const p=FK.plan({...args,...options});totalSolves+=p.endpointSolves;return p;};
  const scheduleBody=arrivalTick=>{
   let state=[...entryBody];
   for(let tick=o.startTick;tick<=lastTick;tick++){
    const f=track[tick],body=f.body,steps=Math.max(1,arrivalTick-tick+1);
    if(tick>o.startTick)state=Body.advance(state,Body.blend(state,bodyDesired,1/steps),o.maxSpineClavicleAngularSpeed);
    body.applied=[...state];body.spineArrivalTick=body.clavicleArrivalTick=arrivalTick;
    body.remainingDegrees=Body.remaining(state,bodyDesired);
    f.pose=Body.apply(bodyContext,f.base,state);body.shoulderDistance=len(sub(f.pose[arm[0]].p,body.clearTarget));
   }
  };
  plan=makePlan({buildGuides:false,earlyArrival:false});
  // Reconcile the FK destination with the scheduled torso pose. Drawing's
  // existing turn-before-grip gate may extend the deadline when capped.
  for(let pass=0;pass<16;pass++){
   const deadline=plan.endTick;scheduleBody(deadline);
   plan=makePlan({minimumEndTick:deadline,buildGuides:false,earlyArrival:false});
   if(plan.endTick===deadline)break;
  }
  scheduleBody(plan.endTick);
  plan=makePlan({minimumEndTick:plan.reachEndTick,beginSlide:(...entry)=>{
   if(o.sheathe)args.beginSlide(...entry);
   const arrivalTick=entry[2],slideTicks=Math.max(1,Math.ceil(track[o.startTick].slideLength/o.slidingSpeed*60));
   for(let tick=arrivalTick;tick<=lastTick;tick++){
    const f=track[tick],progress=clamp((tick-arrivalTick)/slideTicks,0,1);
    f.body.applied=Body.target(bodyContext,o.bodyTargets,o.sheathe?progress:1-progress);
    f.body.desired=[...f.body.applied];f.body.remainingDegrees=0;
    f.pose=Body.apply(bodyContext,f.base,f.body.applied);
    f.body.shoulderDistance=len(sub(f.pose[arm[0]].p,f.body.clearTarget));
   }
  }});
  plan.endpointSolves=totalSolves;
 }
 const frames=[];
 for(let tick=0;tick<=lastTick;tick++){
  const f=track[tick];let pose=f.pose,phase=o.sheathe?'Held':'Holstered',scale=o.sheathe?1:retained,insertion=o.sheathe?0:1,progress=0,metrics=null,goal=f.goalAt(o.sheathe?0:1);
  if(plan&&tick>=o.startTick){
   const armFrame=FK.at(plan,tick);progress=armFrame.progress;
   pose=FK.apply(f.pose,arm,data.parents,armFrame.local);phase='Reach';
   if(o.sheathe)scale=reachScale(o,tick);
   if(plan.arrives&&tick>=plan.endTick){
    phase='Slide';const slide=clamp((tick-plan.endTick)/(plan.slideEnd-plan.endTick),0,1);insertion=o.sheathe?slide:1-slide;goal=f.goalAt(insertion);
    if(o.sheathe)scale=sheathScale(retained,slideEntry,insertion,o.slideRotationCorrection);
    if(tick>=plan.slideEnd){
     if(o.sheathe)phase='Holstered';
     else{
      const grow=o.unshrinkDuration<=0?1:clamp((tick-plan.slideEnd)/60/o.unshrinkDuration,0,1);
      scale=retained+(1-retained)*grow;phase=grow>=1?'Held':'Unshrink';
     }
    }
   }
   const armLength=len(sub(pose[arm[1]].p,pose[arm[0]].p))+len(sub(pose[arm[2]].p,pose[arm[1]].p)),shoulderTarget=len(sub(goal.p,pose[arm[0]].p));
   metrics={armLength,shoulderTarget,unreachable:Math.max(0,shoulderTarget-armLength),handError:len(sub(pose[arm[2]].p,goal.p))};
  }
  const active=['Reach','Slide','Unshrink'].includes(phase),error=metrics?.handError||0;
  const sword=phase==='Holstered'||(phase==='Reach'&&!o.sheathe)?compose(scaledGrip(setup,retained),f.seatHand):phase==='Slide'?compose(scaledGrip(setup,scale),goal):compose(scaledGrip(setup,scale),pose[arm[2]]);
  frames.push({tick,body:f.body,pose,holster:f.holster,sword,goal,commandedHand:plan&&tick>=o.startTick?copy(pose[arm[2]]):null,phase,scale,insertion,progress,active,metrics,handError:error,blocked:phase==='Reach'&&progress>=1&&error>2});
 }
 const locals=frames.map(f=>R.localize(f.pose.map(t=>t.p),f.pose.map(t=>t.q),data.parents));
 return retime({o,motionOffset,sourceFrames:frames,sourceLocals:locals,plan,bladeLength,tip,sheathEntry:slideEntry,names:N,parents:data.parents,arm,pelvis,setup,data,bodyContext,holsterLocal:local,headContext:Head.make(data)},o);
}
const baseMotion=(model,t,gaze=model.o.gazeYaw)=>motion(model.data,model.o.motion,(model.motionOffset||0)+t,gaze);
function headSpeed(o,lookingOut,gaze){
 const key=lookingOut?'maxHeadLookOutVelocity':'maxHeadLookInVelocity';
 return o[key]+(o[key+'AtMaxGaze']-o[key])*clamp(Math.abs(gaze)/170,0,1);
}
function retime(source,input){
 if(input.noCheat||source.tickPlayback)return prepare(source.data,source.setup,input,source.motionOffset||0);
 const o=sanitize(input);
 // A curve/FK edit may arrive while the slider's worker is still rebuilding.
 // A changed holster path needs fresh reach/slide geometry, not cached guides.
 if(o.holsterRotationStabilization!==(source.o.holsterRotationStabilization??0))return prepare(source.data,source.setup,o,source.motionOffset||0);
 const model={...source,o,swordPoint:null,frames:[],headTrack:[],completionTick:null,playbackDuration:o.duration};
 const action=o.sheathe?'sheathe':'draw',reachEnd=Math.min(o.duration,model.plan?model.plan.endTick/60:o.duration);
 model.retimeSegments={reach:{start:o.startTick/60,end:reachEnd,curve:Retime.prepare(o[action+'Curve'])},slide:{start:reachEnd,end:model.plan?.arrives?Math.min(o.duration,model.plan.slideEnd/60):reachEnd,curve:Retime.prepare(o[action+'SlideCurve'])}};
 model.entryInertia=null;model.fkReturn=null;model.armReturn=null;model.gripGuides=null;model.startGaze=o.gazeYaw;
 model.slideGuides=prepareSlideGuides(model,source.slideGuides);
 model.poleGuides=preparePoleGuides(model,source.poleGuides);
 model.entryInertia=prepareEntryInertia(model);
 const profile=o[action+'Return'];
 if(profile.enabled&&model.plan?.arrives&&model.plan.slideEnd/60<o.duration){
  const release=model.plan.slideEnd/60,dt=1e-5;
  const threshold=model.plan.endTick+(model.plan.slideEnd-model.plan.endTick)*profile.startFraction;
  let startTick=model.plan.endTick;
  while(startTick<model.plan.slideEnd&&recordedTime(model,startTick/60)*60<threshold-1e-8)startTick++;
  const start=startTick/60;
  const makeReturn=(time,last,previous)=>({...Return.prepare({names:model.names,parents:model.parents,last,previous,base:baseMotion(model,time),previousBase:baseMotion(model,time-dt),dt,profile,handInertia:!o.sheathe&&time>=release-1e-12}),start:time});
  model.fkReturn=makeReturn(start,sampleSlide(model,start).pose,sampleSlide(model,start-dt).pose);
  if(start<release){
   model.gripBranch=model.names.map((_,j)=>{for(let k=j;k>=0;k=model.parents[k])if(model.names[k]==='clavicle_r')return true;return false;});
   const guides=[],guideRate=240,guideTicks=[];let bodyElapsed=0,previousTick=startTick*4,armSeed=null,poleBasis=null;
   for(let tick=startTick*4;tick<=model.plan.slideEnd*4;tick++)guideTicks.push(tick);
   const correctionTick=(model.plan.endTick+(model.plan.slideEnd-model.plan.endTick)*o.slideRotationCorrection)*4;
   const cutoff=o.slideRotationCorrection===0?correctionTick+4e-6:correctionTick;
   const extraCutoff=model.slideGuides&&cutoff>startTick*4&&cutoff<model.plan.slideEnd*4&&!Number.isInteger(cutoff);
   if(extraCutoff){guideTicks.push(cutoff);guideTicks.sort((a,b)=>a-b);}
   for(const tick of guideTicks){
    const t=tick/guideRate,f=sampleSlide(model,t);
    let pose=f.pose;
    if(tick>startTick*4){
     const base=baseMotion(model,t);
     const at=elapsed=>transplantGrip(model,Return.sample(model.fkReturn,base,elapsed),f.pose);
     const reachable=p=>{
      const a=p[model.arm[0]].p,b=p[model.arm[1]].p,c=p[model.arm[2]].p;
      const upper=len(sub(b,a)),lower=len(sub(c,b)),distance=len(sub(a,f.goal.p));
      return distance>=Math.abs(upper-lower)+.001&&distance<=upper+lower-.001;
     };
     let next=Math.min(t-start,bodyElapsed+(tick-previousTick)/guideRate);pose=at(next);
     // A very early return cannot extend or fold the arm beyond its reach.
     // Pause only the body's return progress at that boundary, then resume on release.
     if(!reachable(pose)){
      let lo=0,hi=next;
      for(let i=0;i<16;i++){const mid=(lo+hi)/2;if(reachable(at(mid)))lo=mid;else hi=mid;}
      next=lo;pose=at(next);
     }
     bodyElapsed=next;pose=pose.map(copy);
     // Destination guides are prepared once. Playback remains parent-local FK.
     if(armSeed)pose=FK.apply(pose,model.arm,model.parents,armSeed);
     solve(pose,model.arm,f.goal);
    }
    const pole=samplePole(model,t);
    if(tick===startTick*4)poleBasis=pole.basis;
    else{const reference=poleReference(model,f,pole);poleBasis=Pole.frame(pose,model.arm,reference,poleBasis);pose=Pole.apply(pose,model.arm,reference,pole.angle,poleBasis);}
    armSeed=FK.capture(pose,model.arm,model.parents);
    guides.push(R.localize(pose.map(p=>p.p),pose.map(p=>p.q),model.parents));
    previousTick=tick;
   }
   model.fkReturn.gripDelay=Math.max(0,release-start-bodyElapsed);
   model.gripGuides={startTick:startTick*4,rate:guideRate,release,guides,ticks:extraCutoff?guideTicks:null};
   model.armReturn=makeReturn(release,sampleBody(model,release).pose,sampleBody(model,release-dt).pose);
  }
 }
 let state=null,lookOutTick=Infinity;
 const threshold=o.sheathe?o.sheatheHeadLookOutThreshold:o.drawHeadLookOutThreshold;
 for(let tick=0;tick<model.sourceFrames.length;tick++){
  const t=tick/60,sourceTime=recordedTime(model,t),f=sampleBody(model,t);
  if(model.plan?.arrives&&sourceTime*60>=model.plan.endTick+(model.plan.slideEnd-model.plan.endTick)*threshold-1e-8&&lookOutTick===Infinity)lookOutTick=tick;
  const seated=seatedSword(model.setup,f.holster),mouth=add(seated.p,rotate(seated.q,had(seated.s,model.setup.baseBladeLocal)));
  const tip=o.sheathe&&o.sheatheHeadTargetAlpha<1?point(f.sword,model.tip):mouth;
  const headTarget=o.sheathe&&o.sheatheHeadTargetAlpha<1?add(tip,mul(sub(mouth,tip),o.sheatheHeadTargetAlpha)):mouth;
  const look=Head.step(model.headContext,f.pose,baseMotion(model,t,0),headTarget,state,{tick,startTick:o.startTick,lookOutTick,maxLookIn:headSpeed(o,false,model.startGaze),maxLookOut:headSpeed(o,true,o.gazeYaw),lookAtAlpha:o.headLookAtAlpha,maxDownAngle:o.headMaxDownAngle,lookInSpeedAlpha:o.headLookInSpeedAlpha,handArrivalTick:model.plan?.arrives?model.plan.endTick:null,lookInExponent:o.headLookInExponent,lookOutExponent:o.headLookOutExponent,neckBase:baseMotion(model,t,0),gazeNeckBase:baseMotion(model,t),lookOutQ:tick>=lookOutTick?baseMotion(model,t)[model.headContext.head].q:null});
  state=look.state;model.headTrack.push({q:state.q,correction:state.correction,parentCorrection:state.parentCorrection,worldDelta:state.worldDelta,baseDelta:state.baseDelta,info:look.info});
  const active=f.active||!look.info.done;
  model.frames.push({...f,tick,pose:look.pose,headLook:look.info,active});
  if(tick>=o.startTick&&!active){model.completionTick=tick;model.playbackDuration=Math.min(o.duration,t);break;}
 }
 return Return.prepareSwordPoint(model,compose,scaledGrip);
}
const blendT=(a,b,t)=>({p:add(a.p,mul(sub(b.p,a.p),t)),q:qslerp(a.q,b.q,t),s:add(a.s,mul(sub(b.s,a.s),t))});
function recordedTime(model,t){
 if(model.tickPlayback)return t;
 for(const segment of Object.values(model.retimeSegments))if(t>segment.start&&t<segment.end)return Retime.time(segment.curve,t,segment.start,segment.end);
 return t;
}
function sampleSource(model,t){
 const raw=clamp(t*60,0,model.sourceFrames.length-1),f=Math.abs(raw-Math.round(raw))<1e-8?Math.round(raw):raw,i=Math.floor(f),a=model.sourceFrames[i],b=model.sourceFrames[Math.min(i+1,model.sourceFrames.length-1)],u=f-i;
 if(u<1e-10)return a;
 const la=model.sourceLocals[i],lb=model.sourceLocals[Math.min(i+1,model.sourceLocals.length-1)],fk=R.fk({q:la.q.map((q,j)=>qslerp(q,lb.q[j],u)),p:la.p.map((p,j)=>R.offsetBlend(p,lb.p[j],u))},model.parents);
 const pose=a.pose.map((p,j)=>({...p,p:fk.points[j],q:fk.q[j]}));let scale=a.scale+(b.scale-a.scale)*u;
 let sword=blendT(a.sword,b.sword,u),goal=blendT(a.goal,b.goal,u);
 const holster=blendT(a.holster,b.holster,u),insertion=a.insertion+(b.insertion-a.insertion)*u;
 if(model.o.sheathe&&a.phase==='Slide'&&model.sheathEntry){scale=sheathScale(1-model.o.shrinkPercent/100,model.sheathEntry,insertion,model.o.slideRotationCorrection);goal=sheathSlideGoal(model.setup,holster,scale,model.tip,model.sheathEntry,insertion,model.o.slideRotationCorrection);sword=compose(scaledGrip(model.setup,scale),goal);}
 if(a.phase==='Held'||a.phase==='Unshrink'||(a.phase==='Reach'&&model.o.sheathe))sword=compose(scaledGrip(model.setup,scale),pose[model.arm[2]]);
 const body=a.body&&b.body?{...a.body,applied:Body.blend(a.body.applied,b.body.applied,u)}:a.body;
 return {...a,body,pose,scale,sword,holster,goal,insertion};
}
// Only the authored body turn/arm pose uses the curved clock. Carry it on the
// current locomotion pose; the pelvis and its holster never follow that clock.
function motionFrame(model,t){
 const sourceTime=recordedTime(model,t);let f=sampleSource(model,sourceTime);
 if(model.o.sheathe&&(f.phase==='Held'||f.phase==='Reach')){
  const scale=reachScale(model.o,t*60);
  f={...f,scale,sword:compose(scaledGrip(model.setup,scale),f.pose[model.arm[2]])};
 }
 if(Math.abs(sourceTime-t)<1e-12&&Math.abs(t*60-Math.round(t*60))<1e-8)return f;
 const base=baseMotion(model,t);
 let pose=f.body?Body.apply(model.bodyContext,base,f.body.applied):base;
 if(model.plan&&sourceTime*60>=model.o.startTick)pose=FK.apply(pose,model.arm,model.parents,FK.capture(f.pose,model.arm,model.parents));
 const holster=compose(model.holsterLocal,base[model.pelvis]),delta=unit(qm(holster.q,qinv(f.holster.q)));
 const carry=v=>({...v,p:add(holster.p,rotate(delta,sub(v.p,f.holster.p))),q:unit(qm(delta,v.q))});
 const goal=carry(f.goal),held=f.phase==='Held'||f.phase==='Unshrink'||(f.phase==='Reach'&&model.o.sheathe);
 const sword=held?compose(scaledGrip(model.setup,f.scale),pose[model.arm[2]]):carry(f.sword);
 const handError=len(sub(pose[model.arm[2]].p,goal.p));
 return {...f,pose,holster,goal,sword,handError,commandedHand:f.commandedHand?copy(pose[model.arm[2]]):null,metrics:f.metrics?{...f.metrics,handError}:null};
}
// Insertion uses the slide curve; alignment has its own elapsed clock.
function slideFrame(model,t){
 const f=motionFrame(model,t),p=model.plan;
 if(!model.o.sheathe||!model.slideGuides||t*60<=p.endTick||t*60>=p.slideEnd)return f;
 const rotationProgress=(t*60-p.endTick)/(p.slideEnd-p.endTick);
 const goal=sheathSlideGoal(model.setup,f.holster,f.scale,model.tip,model.sheathEntry,f.insertion,model.o.slideRotationCorrection,rotationProgress);
 return {...f,goal,sword:compose(scaledGrip(model.setup,f.scale),goal)};
}
function prepareSlideGuides(model,cached){
 const {o,plan:p}=model;
 if(!p?.arrives||model.retimeSegments.slide.curve.identity)return null;
 const key=JSON.stringify([o.sheathe,o[o.sheathe?'sheatheSlideCurve':'drawSlideCurve'],o.slideRotationCorrection]);
 if(cached?.key===key)return cached;
 const end=Math.min(p.slideEnd,model.sourceFrames.length-1),keys=[],ticks=[];
 for(let tick=p.endTick;tick<=end;tick+=.25)ticks.push(tick);
 // Include the exact angular cutoff, even between quarter ticks. Zero requests
 // the existing immediate-after-entry correction, so give it an immediate key.
 const cutoff=p.endTick+(p.slideEnd-p.endTick)*o.slideRotationCorrection;
 if(o.sheathe&&cutoff<=end)ticks.push(cutoff>p.endTick?cutoff:p.endTick+1e-6);
 ticks.push(end);ticks.sort((a,b)=>a-b);
 model.slideGuides={key,keys};let seed=null;
 for(const tick of [...new Set(ticks)]){
  const f=slideFrame(model,tick/60);
  let pose=f.pose;
  if(seed){pose=FK.apply(pose,model.arm,model.parents,seed);solve(pose,model.arm,f.goal);}
  seed=FK.capture(pose,model.arm,model.parents);keys.push({tick,local:seed});
 }
 return model.slideGuides;
}
function samplePlannedArm(model,t){
 const f=slideFrame(model,t),guides=model.slideGuides,tick=t*60;
 if(!guides||tick<=model.plan.endTick)return f;
 const keys=guides.keys;let lo=0,hi=keys.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(keys[mid].tick<tick)lo=mid;else hi=mid;}
 const a=keys[lo],b=keys[hi],u=clamp((tick-a.tick)/Math.max(1e-12,b.tick-a.tick),0,1);
 const pose=FK.apply(f.pose,model.arm,model.parents,FK.blend(a.local,b.local,u));
 const handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 return {...f,pose,handError,commandedHand:copy(pose[model.arm[2]]),metrics:f.metrics?{...f.metrics,handError}:null};
}
function preparePoleGuides(model,cached){
 const key=JSON.stringify([model.o.bodyTargets,model.o.maxElbowPoleAngularSpeed,model.o.swordRelativeSlidePole,model.o.drawCurve,model.o.sheatheCurve,model.o.drawSlideCurve,model.o.sheatheSlideCurve]);
 if(cached?.key===key)return cached;
 if(!model.plan)return null;
 const keys=[],start=model.o.startTick,end=Math.min(model.plan.arrives?model.plan.slideEnd:model.o.duration*60,model.o.duration*60);
 const entry=model.plan.endTick,useSword=model.o.swordRelativeSlidePole&&model.plan.arrives;
 // Arrival is an integer tick, so the existing quarter-tick track includes it exactly.
 let basis=null,angle=0,swordDown=null,reachSpeed=model.o.maxElbowPoleAngularSpeed;
 const reachTarget=Pole.target(model.o.bodyTargets,model.o.sheathe?0:1);
 for(let tick=start;tick<=end+1e-8;tick+=.25){
  const f=samplePlannedArm(model,tick/60);
  if(useSword&&tick>=entry&&!swordDown){
   // Capture the existing zero direction in sword space at the exact transfer.
   // Only the reference changes; the elbow angle and physical pose are continuous.
   basis=Pole.frame(f.pose,model.arm,model.bodyContext.top,basis);
   const toSword=qm(qinv(f.sword.q),f.pose[model.bodyContext.top].q);
   basis={d:rotate(toSword,basis.d),zero:rotate(toSword,basis.zero)};
   swordDown=basis.zero;
  }
  const reference=swordDown?{q:f.sword.q,down:swordDown}:model.bodyContext.top;
  basis=Pole.frame(f.pose,model.arm,reference,basis);
  if(tick===start){
   angle=Pole.measure(f.pose,model.arm,reference,basis);
   // Use the available reach time, with the knob as a ceiling. Curves do not
   // change this clock; a capped pole continues catching up during sliding.
   if(model.plan.arrives&&entry>start)reachSpeed=Math.min(reachSpeed,Math.abs(Pole.wrap(reachTarget-angle))*60/(entry-start));
  }else angle=Pole.advance(angle,tick<=entry?reachTarget:Pole.target(model.o.bodyTargets,f.insertion),tick<=entry?reachSpeed:model.o.maxElbowPoleAngularSpeed,1/240);
  const pose=Pole.apply(f.pose,model.arm,reference,angle,basis);
  keys.push({tick,angle,basis,swordDown,local:FK.capture(pose,model.arm,model.parents)});
 }
 return {key,keys};
}
function samplePole(model,t){
 const keys=model.poleGuides.keys,x=clamp((t*60-keys[0].tick)*4,0,keys.length-1),i=Math.floor(x),a=keys[i],b=keys[Math.min(i+1,keys.length-1)],u=x-i;
 return {angle:a.angle+(b.angle-a.angle)*u,basis:a.basis,swordDown:a.swordDown,local:FK.blend(a.local,b.local,u)};
}
const poleReference=(model,f,pole)=>pole.swordDown?{q:f.sword.q,down:pole.swordDown}:model.bodyContext.top;
function correctPole(model,f,t){
 if(!model.poleGuides||t*60<=model.o.startTick||t*60>model.plan.slideEnd)return f;
 const pole=samplePole(model,t),reference=poleReference(model,f,pole),basis=Pole.frame(f.pose,model.arm,reference,pole.basis);
 const pose=Pole.apply(f.pose,model.arm,reference,pole.angle,basis);
 // This is only a rigid swivel about the current shoulder/wrist axis: no hand
 // target solve. It removes tiny angle errors introduced by FK guide sampling.
 return {...f,pose};
}
function sampleSlide(model,t){
 const f=samplePlannedArm(model,t);
 if(!model.poleGuides||t*60<=model.o.startTick)return applyEntryInertia(model,f,t);
 const pole=samplePole(model,t),pose=FK.apply(f.pose,model.arm,model.parents,pole.local),handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 const held=f.phase==='Held'||f.phase==='Unshrink'||(f.phase==='Reach'&&model.o.sheathe);
 // Entry inertia owns the final FK residual, including the elbow. Applying the
 // pole correction afterwards would erase the incoming arm angular velocity.
 return applyEntryInertia(model,correctPole(model,{...f,pose,elbowPoleAngle:pole.angle,sword:held?compose(scaledGrip(model.setup,f.scale),pose[model.arm[2]]):f.sword,handError,metrics:f.metrics?{...f.metrics,handError}:null},t),t);
}
// Match incoming local FK velocity, then retire the residual on an unwarped
// clock. Include driven ancestors so a new torso turn cannot kick the hand.
function prepareEntryInertia(model){
 const {o}=model,start=o.startTick/60,duration=Math.min(o.entryInertiaDuration,model.retimeSegments.reach.end-start);
 if(o.entryInertia<=0||duration<=0)return null;
 const dt=1e-4,local=pose=>R.localize(pose.map(p=>p.p),pose.map(p=>p.q),model.parents);
 const before=local(baseMotion(model,Math.max(-(model.motionOffset||0),start-dt))),first=local(sampleSlide(model,start).pose),next=local(sampleSlide(model,start+dt).pose);
 const ctx=model.bodyContext,seeds=ctx.inertiaBones.map(j=>{
  const incoming=R.qlog(qm(qinv(before.q[j]),first.q[j])),outgoing=R.qlog(qm(qinv(first.q[j]),next.q[j]));
  const pIn=R.qlog(fromTo(before.p[j],first.p[j])),pOut=R.qlog(fromTo(first.p[j],next.p[j]));
  return {j,q:mul(sub(incoming,outgoing),o.entryInertia/dt),p:mul(sub(pIn,pOut),o.entryInertia/dt)};
 }).filter(v=>len(v.q)>1e-6||len(v.p)>1e-6);
 return {start,duration,seeds};
}
function applyEntryInertia(model,f,t){
 const entry=model.entryInertia,elapsed=entry?t-entry.start:0;
 if(!entry||elapsed<=0||elapsed>=entry.duration-1e-12||f.phase!=='Reach')return f;
 const momentum=elapsed*Math.pow(1-elapsed/entry.duration,3);
 const local=R.localize(f.pose.map(p=>p.p),f.pose.map(p=>p.q),model.parents);
 for(const v of entry.seeds){local.q[v.j]=unit(qm(local.q[v.j],R.qexp(mul(v.q,momentum))));local.p[v.j]=rotate(R.qexp(mul(v.p,momentum)),local.p[v.j]);}
 const fk=R.fk(local,model.parents),pose=f.pose.slice();
 for(const j of model.bodyContext.affected)pose[j]={...pose[j],p:fk.points[j],q:fk.q[j]};
 const handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 return {...f,pose,sword:model.o.sheathe?compose(scaledGrip(model.setup,f.scale),pose[model.arm[2]]):f.sword,handError,metrics:f.metrics?{...f.metrics,handError}:null};
}
function sampleBody(model,t){
 if(model.tickPlayback)return Online.sample(model,t);
 const f=sampleSlide(model,t),ret=model.fkReturn;
 if(!ret||t<ret.start)return f;
 const grip=model.gripGuides,arm=model.armReturn,elapsed=t-ret.start-(grip&&t>=grip.release?ret.gripDelay:0);
 const armActive=arm&&t-arm.start<arm.timing.duration-1e-12,returnActive=elapsed<ret.timing.duration-1e-12||!!armActive;
 let pose=f.pose;
 if(grip&&t<=grip.release){
  const x=clamp(t*grip.rate-grip.startTick,0,grip.guides.length-1);let i=Math.floor(x),u=x-i;
  if(grip.ticks){let lo=0,hi=grip.ticks.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(grip.ticks[mid]<t*grip.rate)lo=mid;else hi=mid;}i=lo;u=clamp((t*grip.rate-grip.ticks[lo])/(grip.ticks[hi]-grip.ticks[lo]),0,1);}
  const a=grip.guides[i],b=grip.guides[Math.min(i+1,grip.guides.length-1)];
  const lower=R.localize(f.pose.map(p=>p.p),f.pose.map(p=>p.q),model.parents);
  const offsets=a.p.map((p,j)=>{
   if(!ret.model.upper[j])return lower.p[j];
   const v=R.offsetBlend(p,b.p[j],u);
   // Preserve the current source lengths across the differently spaced guides.
   return model.gripBranch[j]?mul(unit(v),len(lower.p[j])):v;
  });
  const fk=R.fk({q:a.q.map((q,j)=>ret.model.upper[j]?qslerp(q,b.q[j],u):lower.q[j]),p:offsets},model.parents);
  pose=pose.map((p,j)=>({...p,p:fk.points[j],q:fk.q[j]}));
 }else{
  const base=baseMotion(model,t);
  pose=elapsed===0?f.pose:Return.sample(ret,base,elapsed);
  if(arm&&returnActive)pose=transplantGrip(model,pose,Return.sample(arm,base,t-arm.start));
 }
 const gripping=grip&&t<grip.release;
 if(t>model.plan.slideEnd/60)pose=Return.applyArmIK(arm||ret,baseMotion(model,t),arm?t-arm.start:elapsed,pose,solve);
 if((arm||ret).handRotation&&t>model.plan.slideEnd/60)pose=Return.applyHandRotation(arm||ret,baseMotion(model,t),arm?t-arm.start:elapsed,pose);
 const sword=model.o.sheathe||gripping?f.sword:compose(scaledGrip(model.setup,f.scale),pose[model.arm[2]]);
 const handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 const result={...f,pose,sword,handError,metrics:f.metrics?{...f.metrics,handError}:null,phase:gripping?'Slide':returnActive?'FK return':f.phase,active:f.active||returnActive,fkReturn:{elapsed,duration:ret.timing.duration,active:returnActive,gripping:!!gripping,armStart:arm?.start}};
 return Return.applySwordPoint(model,grip&&t<=grip.release?correctPole(model,result,t):result,t,compose,scaledGrip);
}
function transplantGrip(model,body,donor){
 const local=pose=>R.localize(pose.map(p=>p.p),pose.map(p=>p.q),model.parents),a=local(body),b=local(donor);
 const fk=R.fk({q:a.q.map((q,j)=>model.gripBranch[j]?b.q[j]:q),p:a.p.map((p,j)=>model.gripBranch[j]?b.p[j]:p)},model.parents);
 return body.map((p,j)=>model.gripBranch[j]?{...p,p:fk.points[j],q:fk.q[j]}:p);
}
function sample(model,t){
 if(model.tickPlayback)return Online.sample(model,t);
 t=clamp(t,0,model.playbackDuration);
 const x=Math.min(t*60,model.headTrack.length-1),i=Math.floor(x),u=x-i;
 if(u<1e-10)return model.frames[i];
 const f=sampleBody(model,t),a=model.headTrack[i],b=model.headTrack[Math.min(i+1,model.headTrack.length-1)];
 const reference=add(a.correction,mul(sub(b.correction,a.correction),u));
 const parentReference=a.parentCorrection.map((v,k)=>v+(b.parentCorrection[k]-v)*u);
 const frameDeltas={head:a.worldDelta.map((v,k)=>v+(b.worldDelta[k]-v)*u),base:a.baseDelta.map((v,k)=>v+(b.baseDelta[k]-v)*u)};
 const pose=t*60<=model.o.startTick?f.pose:Head.apply(model.headContext,f.pose,qslerp(a.q,b.q,u),reference,baseMotion(model,t,0),baseMotion(model,t),model.o.headMaxDownAngle,parentReference,frameDeltas);
 return {...f,pose,headLook:a.info,active:f.active||!a.info.done};
}
function previewTime(model,insertion){
 const p=model.plan;if(!p)return Math.min(model.o.startTick/60,model.playbackDuration);
 const start=model.sheathEntry?.insertion??0;
 const progress=model.o.sheathe?clamp((insertion-start)/Math.max(1e-8,1-start),0,1):1-insertion,segment=model.retimeSegments.slide;
 let lo=0,hi=1;
 for(let i=0;i<32;i++){const mid=(lo+hi)/2;if(Retime.sample(segment.curve,mid)<progress)lo=mid;else hi=mid;}
 return Math.min(model.playbackDuration,model.fkReturn?.start??Infinity,(p.endTick+(p.slideEnd-p.endTick)*(progress<=0?0:progress>=1?1:(lo+hi)/2))/60);
}
function previewBody(model,insertion,targets=model.o.bodyTargets,time=previewTime(model,insertion)){
 const t=clamp(time,0,model.playbackDuration),f=sample(model,t),ctx=model.bodyContext;
 const planned=Body.target(ctx,model.o.bodyTargets,f.insertion),edited=Body.target(ctx,targets,f.insertion);
 const poleDelta=Pole.wrap(Pole.target(targets,f.insertion)-Pole.target(model.o.bodyTargets,f.insertion));
 if(Body.remaining(planned,edited)<1e-5&&Math.abs(poleDelta)<1e-7)return {...f,previewTime:t};
 // During a drag carry the playback arm with the edited body. Never invent a
 // second elbow solution. The worker supplies the exact updated motion on release.
 const adjusted=[0,4,8].flatMap((k,i)=>unit(qm(qm(edited.slice(k,k+4),qinv(planned.slice(k,k+4))),ctx.reference[i])));
 let pose=Body.adjust(ctx,f.pose,adjusted);
 const initial=Pole.frame(f.pose,model.arm,ctx.top),pole=model.poleGuides?samplePole(model,t):{angle:Pole.measure(f.pose,model.arm,ctx.top,initial),basis:initial},reference=poleReference(model,f,pole),basis=Pole.frame(pose,model.arm,reference,pole.basis);
 pose=Pole.apply(pose,model.arm,reference,pole.angle+poleDelta,basis);
 const handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 return {...f,pose,handError,previewTime:t,previewPending:true};
}
function blendPreview(previous,next,alpha,parents){
 if(!previous)return {frame:next,settled:true};
 let error=0;
 for(let j=0;j<next.pose.length;j++)error=Math.max(error,angle(previous.pose[j].q,next.pose[j].q),len(sub(previous.pose[j].p,next.pose[j].p)));
 for(const key of ['sword','holster'])error=Math.max(error,angle(previous[key].q,next[key].q),len(sub(previous[key].p,next[key].p)));
 if(error<.005)return {frame:next,settled:true};
 const local=f=>R.localize(f.pose.map(v=>v.p),f.pose.map(v=>v.q),parents),a=local(previous),b=local(next);
 const fk=R.fk({q:a.q.map((q,j)=>qslerp(q,b.q[j],alpha)),p:a.p.map((p,j)=>parents[j]<0?add(p,mul(sub(b.p[j],p),alpha)):R.offsetBlend(p,b.p[j],alpha))},parents);
 const transform=(a,b)=>({...b,p:add(a.p,mul(sub(b.p,a.p),alpha)),q:qslerp(a.q,b.q,alpha),s:(b.s||[1,1,1]).map((v,k)=>(a.s?.[k]??1)+(v-(a.s?.[k]??1))*alpha)});
 return {frame:{...next,pose:next.pose.map((v,j)=>({...v,p:fk.points[j],q:fk.q[j]})),sword:transform(previous.sword,next.sword),holster:transform(previous.holster,next.holster)},settled:false};
}
const api={holsterPivot,reachScale,headSpeed,seatedSword,sheathSlideGoal,gazePose,bladeTip,point,handForTip,defaults,sanitize,prepare,sample,sampleBody,previewTime,previewBody,blendPreview,retime,recordedTime,motion,solve,compose,scaledGrip,seatHandAtScale,angle};if(typeof module!=='undefined')module.exports=api;else root.Holster=api;
})(globalThis);
