/* Deterministic 60-tick D/S pose model. UE coordinates and centimetres internally. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const Retime=typeof module!=='undefined'?require('./retime.js'):root.Retime;
const FK=typeof module!=='undefined'?require('./armfk.js'):root.ArmFK;
const Return=typeof module!=='undefined'?require('./fkreturn.js'):root.FKReturn;
const Head=typeof module!=='undefined'?require('./headlook.js'):root.HeadLook;
const Body=typeof module!=='undefined'?require('./bodyreach.js'):root.BodyReach;
const {add,sub,mul,dot,cross,length:len,unit,qm,qinv,rotate,qslerp,fromTo,toAxes}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),I=[0,0,0,1];
const had=(a,b)=>a.map((x,i)=>x*b[i]);
const copy=t=>({p:[...t.p],q:[...t.q],s:[...(t.s||[1,1,1])]});
const compose=(a,b)=>({p:add(b.p,rotate(b.q,had(b.s||[1,1,1],a.p))),q:unit(qm(b.q,a.q)),s:had(a.s||[1,1,1],b.s||[1,1,1])});
const angle=(a,b)=>2*Math.acos(clamp(Math.abs(dot(a,b)),-1,1))*180/Math.PI;
const defaults={motion:'idle',sheathe:true,startTick:25,maxReachSpeed:100,maxReachRotationSpeed:180,slidingSpeed:60,shrinkPercent:35,unshrinkDuration:.5,holsterX:0,holsterY:0,holsterZ:0,holsterPitch:0,holsterYaw:0,holsterRoll:0,duration:8,spineClavicleAngleLimit:45,maxSpineClavicleAngularSpeed:90,drawReturn:Return.defaults(),sheatheReturn:Return.defaults(),headLookAtAlpha:1,headLookInExponent:1,headLookOutExponent:1,maxHeadLookInVelocity:180,maxHeadLookOutVelocity:180,drawHeadLookOutThreshold:.3,sheatheHeadLookOutThreshold:.5,drawCurve:Retime.linear(),sheatheCurve:Retime.linear(),drawSlideCurve:Retime.linear(),sheatheSlideCurve:Retime.linear()};
function sanitize(input){const o={...defaults,...input};for(const k of Object.keys(defaults))if(typeof defaults[k]==='number')o[k]=Number.isFinite(Number(o[k]))?Number(o[k]):defaults[k];o.startTick=Math.round(clamp(o.startTick,0,3600));o.duration=clamp(o.duration,1,60);o.shrinkPercent=clamp(o.shrinkPercent,0,99.9);o.unshrinkDuration=clamp(o.unshrinkDuration,0,10);for(const k of ['maxReachSpeed','maxReachRotationSpeed','slidingSpeed'])o[k]=clamp(o[k],.01,10000);o.spineClavicleAngleLimit=clamp(o.spineClavicleAngleLimit,0,90);o.maxSpineClavicleAngularSpeed=clamp(o.maxSpineClavicleAngularSpeed,.01,10000);o.drawReturn=Return.sanitize(o.drawReturn);o.sheatheReturn=Return.sanitize(o.sheatheReturn);delete o.headCorrectionAlpha;for(const k of ['headLookInExponent','headLookOutExponent'])o[k]=clamp(o[k],1,8);o.headLookAtAlpha=clamp(o.headLookAtAlpha,0,1);for(const k of ['maxHeadLookInVelocity','maxHeadLookOutVelocity'])o[k]=clamp(o[k],.01,10000);for(const k of ['drawHeadLookOutThreshold','sheatheHeadLookOutThreshold'])o[k]=clamp(o[k],0,1);o.motion=o.motion==='walk'?'walk':'idle';o.sheathe=!!o.sheathe;o.drawCurve=Retime.sanitize(o.drawCurve);o.sheatheCurve=Retime.sanitize(o.sheatheCurve);o.drawSlideCurve=Retime.sanitize(o.drawSlideCurve);o.sheatheSlideCurve=Retime.sanitize(o.sheatheSlideCurve);return o;}
function euler(p,y,r){return qm(qm(R.qexp([0,0,y*Math.PI/180]),R.qexp([0,-p*Math.PI/180,0])),R.qexp([-r*Math.PI/180,0,0]));}
function motion(data,key,t){
 const clip=data.motions[key],duration=clip.duration,u=(t%duration)*data.fps,i=Math.min(clip.frames.length-2,Math.floor(u)),v=u-i;
 const frames=clip.frames,first=frames[0][0],last=frames.at(-1)[0],loops=Math.floor(t/duration),drift=mul(sub(last.slice(0,3),first.slice(0,3)),loops);
 const rootNow=add(frames[i][0].slice(0,3),mul(sub(frames[i+1][0].slice(0,3),frames[i][0].slice(0,3)),v));
 return frames[i].map((a,j)=>({p:sub(add(a.slice(0,3),mul(sub(frames[i+1][j].slice(0,3),a.slice(0,3)),v)),[rootNow[0],rootNow[1],0]),q:qslerp(a.slice(3),frames[i+1][j].slice(3),v),s:[1,1,1]}));
}
function scaledGrip(setup,scale){const g=copy(setup.grip);g.p=rotate(g.q,had(rotate(qinv(g.q),g.p),[1,1,scale]));g.s=had(setup.assetScale,[1,1,scale]);return g;}
function seatHandAtScale(setup,full,scale){
 // Keep the authored blade-base point seated while shortening about the grip.
 // Reusing the full-size hand transform would lift the shortened base off the mouth.
 const grip=scaledGrip(setup,scale),q=unit(qm(full.q,qinv(grip.q)));
 const seatedBase=add(full.p,rotate(full.q,had(full.s,setup.baseBladeLocal)));
 const swordOrigin=sub(seatedBase,rotate(full.q,had(grip.s,setup.baseBladeLocal)));
 return {p:sub(swordOrigin,rotate(q,grip.p)),q,s:[1,1,1]};
}
function solve(pose,idx,goal){
 const [s,e,h]=idx,A=pose[s].p,B=pose[e].p,C=pose[h].p,L1=len(sub(B,A)),L2=len(sub(C,B));
 const delta=sub(goal.p,A),direction=len(delta)>1e-8?unit(delta):[1,0,0],distance=len(delta),D=clamp(distance,Math.abs(L1-L2)+.001,L1+L2-.001);
 let pole=sub(sub(B,A),mul(direction,dot(sub(B,A),direction)));
 if(len(pole)<1e-7)pole=cross(direction,Math.abs(direction[2])<.9?[0,0,1]:[0,1,0]);pole=unit(pole);
 const along=(L1*L1+D*D-L2*L2)/(2*D),E=add(add(A,mul(direction,along)),mul(pole,Math.sqrt(Math.max(0,L1*L1-along*along)))),H=add(A,mul(direction,D));
 pose[s].q=unit(qm(fromTo(sub(B,A),sub(E,A)),pose[s].q));pose[e].q=unit(qm(fromTo(sub(C,B),sub(H,E)),pose[e].q));pose[e].p=E;pose[h].p=H;pose[h].q=[...goal.q];
 return {armLength:L1+L2,shoulderTarget:distance,unreachable:Math.max(0,distance-L1-L2),handError:len(sub(H,goal.p))};
}
function prepare(data,setup,input){
 const o=sanitize(input),N=data.names,arm=['upperarm_r','lowerarm_r','hand_r'].map(x=>N.indexOf(x)),pelvis=N.indexOf('pelvis');
 const bladeLength=setup.bladeLength,retained=1-o.shrinkPercent/100,lastTick=Math.ceil(o.duration*60),bodyContext=Body.make(data,motion(data,o.motion,0));
 const local=copy(setup.holster);local.p=add(local.p,[o.holsterX,o.holsterY,o.holsterZ]);local.q=unit(qm(euler(o.holsterPitch,o.holsterYaw,o.holsterRoll),local.q));
 const track=[];let bodyState=[0,0,0],bodyDesired=[0,0,0];
 for(let tick=0;tick<=lastTick;tick++){
  const base=motion(data,o.motion,tick/60),holster=compose(local,base[pelvis]),full=compose(setup.seated,holster);
  const seatHand=seatHandAtScale(setup,full,retained);
  const goalAt=x=>({...copy(seatHand),p:sub(seatHand.p,mul(rotate(full.q,[0,0,1]),bladeLength*retained*(1-x)))});
  let pose=base,body=null;
  if(tick>=o.startTick){
   const clearTarget=goalAt(0).p;
   bodyDesired=Body.optimize(bodyContext,base,clearTarget,bodyDesired,o.spineClavicleAngleLimit);
   bodyState=Body.advance(bodyState,bodyDesired,o.maxSpineClavicleAngularSpeed);pose=Body.apply(bodyContext,base,bodyState);
   body={applied:[...bodyState],desired:[...bodyDesired],remainingDegrees:Body.remaining(bodyState,bodyDesired),clearTarget,
    baseShoulderDistance:len(sub(base[arm[0]].p,clearTarget)),shoulderDistance:len(sub(pose[arm[0]].p,clearTarget))};
  }
  track.push({base,pose,body,holster,seatHand,goalAt,slideLength:bladeLength*retained});
 }
 const frameAt=t=>track[clamp(Math.round(t),0,lastTick)];
 let plan=null;
 if(o.startTick<=lastTick){
  const args={arm,parents:data.parents,frameAt,startTick:o.startTick,lastTick,o,solve};
  let totalSolves=0;
  const makePlan=options=>{const p=FK.plan({...args,...options});totalSolves+=p.endpointSolves;return p;};
  const scheduleBody=arrivalTick=>{
   let state=[0,0,0],clavicleAtArrival=null;const cap=o.maxSpineClavicleAngularSpeed*Math.PI/180/60;
   const slideTicks=Math.max(1,Math.ceil(track[o.startTick].slideLength/o.slidingSpeed*60));
   const arrivalDesired=frameAt(arrivalTick).body.desired;
   for(let tick=o.startTick;tick<=lastTick;tick++){
    const f=track[tick],body=f.body;
    // Spread both remaining turns across the remaining reach ticks, rather than
    // turning at maximum speed and waiting. Moving targets still obey the cap.
    const steps=Math.max(1,arrivalTick-tick+1);
    // Aim at the known arrival pose, so gait changes do not leave a last-tick
    // catch-up rotation. Resume following the moving optimum after arrival.
    const target=tick<=arrivalTick?arrivalDesired:body.desired;
    const wanted=target.map((v,k)=>tick===o.startTick?0:(v-state[k])/steps);
    state=Body.advance(state,state.map((v,k)=>v+wanted[k]),o.maxSpineClavicleAngularSpeed);
    if(tick===arrivalTick)clavicleAtArrival=state.slice(1);
    const release=o.sheathe&&clavicleAtArrival?clamp((tick-arrivalTick)/slideTicks,0,1):0;
    body.applied=[state[0],...(clavicleAtArrival&&o.sheathe?clavicleAtArrival.map(v=>v*(1-release)||0):state.slice(1))];
    body.clavicleRelease=release;body.spineArrivalTick=body.clavicleArrivalTick=arrivalTick;
    body.spineSpeedLimited=Math.abs(wanted[0])>cap+1e-12;
    body.clavicleSpeedLimited=Math.hypot(wanted[1],wanted[2])>cap+1e-12;
    body.remainingDegrees=Body.remaining(body.applied,body.desired);
    f.pose=Body.apply(bodyContext,f.base,body.applied);
    body.shoulderDistance=len(sub(f.pose[arm[0]].p,body.clearTarget));
   }
  };
  plan=makePlan({buildGuides:false});
  // Reconcile the FK destination with the scheduled torso pose. Drawing's
  // existing turn-before-grip gate may extend the deadline when capped.
  for(let pass=0;pass<16;pass++){
   const deadline=plan.endTick;scheduleBody(deadline);
   plan=makePlan({minimumEndTick:deadline,buildGuides:false});
   if(plan.endTick===deadline)break;
  }
  scheduleBody(plan.endTick);
  plan=makePlan({minimumEndTick:plan.endTick});
  plan.endpointSolves=totalSolves;
 }
 const frames=[];
 for(let tick=0;tick<=lastTick;tick++){
  const f=track[tick];let pose=f.pose,phase=o.sheathe?'Held':'Holstered',scale=o.sheathe?1:retained,insertion=o.sheathe?0:1,progress=0,metrics=null,goal=f.goalAt(o.sheathe?0:1);
  if(plan&&tick>=o.startTick){
   const armFrame=FK.at(plan,tick);progress=armFrame.progress;
   pose=FK.apply(f.pose,arm,data.parents,armFrame.local);phase='Reach';
   if(o.sheathe)scale=1-o.shrinkPercent/100*progress;
   if(plan.arrives&&tick>=plan.endTick){
    phase='Slide';const slide=clamp((tick-plan.endTick)/(plan.slideEnd-plan.endTick),0,1);insertion=o.sheathe?slide:1-slide;goal=f.goalAt(insertion);
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
 return retime({o,sourceFrames:frames,sourceLocals:locals,plan,bladeLength,names:N,parents:data.parents,arm,pelvis,setup,data,headContext:Head.make(data)},o);
}
function retime(source,input){
 const o=sanitize(input),model={...source,o,frames:[],headTrack:[],completionTick:null,playbackDuration:o.duration};
 const action=o.sheathe?'sheathe':'draw',reachEnd=Math.min(o.duration,model.plan?model.plan.endTick/60:o.duration);
 model.retimeSegments={reach:{start:o.startTick/60,end:reachEnd,curve:Retime.prepare(o[action+'Curve'])},slide:{start:reachEnd,end:model.plan?.arrives?Math.min(o.duration,model.plan.slideEnd/60):reachEnd,curve:Retime.prepare(o[action+'SlideCurve'])}};
 model.fkReturn=null;
 const profile=o[action+'Return'];
 if(profile.enabled&&model.plan?.arrives&&model.plan.slideEnd/60<o.duration){
  const start=model.plan.slideEnd/60,dt=1e-5;
  model.fkReturn={...Return.prepare({names:model.names,parents:model.parents,last:sampleSource(model,start).pose,previous:sampleSource(model,recordedTime(model,start-dt)).pose,base:motion(model.data,o.motion,start),previousBase:motion(model.data,o.motion,start-dt),dt,profile}),start};
 }
 let state=null,lookOutTick=Infinity;
 const threshold=o.sheathe?o.sheatheHeadLookOutThreshold:o.drawHeadLookOutThreshold;
 for(let tick=0;tick<model.sourceFrames.length;tick++){
  const t=tick/60,sourceTime=recordedTime(model,t),f=sampleBody(model,t);
  if(model.plan?.arrives&&sourceTime*60>=model.plan.endTick+(model.plan.slideEnd-model.plan.endTick)*threshold-1e-8&&lookOutTick===Infinity)lookOutTick=tick;
  const seated=compose(model.setup.seated,f.holster),mouth=add(seated.p,rotate(seated.q,had(seated.s,model.setup.baseBladeLocal)));
  const look=Head.step(model.headContext,f.pose,motion(model.data,o.motion,t),mouth,state,{tick,startTick:o.startTick,lookOutTick,maxLookIn:o.maxHeadLookInVelocity,maxLookOut:o.maxHeadLookOutVelocity,lookAtAlpha:o.headLookAtAlpha,lookInExponent:o.headLookInExponent,lookOutExponent:o.headLookOutExponent});
  state=look.state;model.headTrack.push({q:state.q,info:look.info});
  const active=f.active||!look.info.done;
  model.frames.push({...f,tick,pose:look.pose,headLook:look.info,active});
  if(tick>=o.startTick&&!active){model.completionTick=tick;model.playbackDuration=Math.min(o.duration,t);break;}
 }
 return model;
}
const blendT=(a,b,t)=>({p:add(a.p,mul(sub(b.p,a.p),t)),q:qslerp(a.q,b.q,t),s:add(a.s,mul(sub(b.s,a.s),t))});
function recordedTime(model,t){
 for(const segment of Object.values(model.retimeSegments))if(t>segment.start&&t<segment.end)return Retime.time(segment.curve,t,segment.start,segment.end);
 return t;
}
function sampleSource(model,t){
 const raw=clamp(t*60,0,model.sourceFrames.length-1),f=Math.abs(raw-Math.round(raw))<1e-8?Math.round(raw):raw,i=Math.floor(f),a=model.sourceFrames[i],b=model.sourceFrames[Math.min(i+1,model.sourceFrames.length-1)],u=f-i;
 if(u<1e-10)return a;
 const la=model.sourceLocals[i],lb=model.sourceLocals[Math.min(i+1,model.sourceLocals.length-1)],fk=R.fk({q:la.q.map((q,j)=>qslerp(q,lb.q[j],u)),p:la.p.map((p,j)=>R.offsetBlend(p,lb.p[j],u))},model.parents);
 const pose=a.pose.map((p,j)=>({...p,p:fk.points[j],q:fk.q[j]})),scale=a.scale+(b.scale-a.scale)*u;
 let sword=blendT(a.sword,b.sword,u);
 if(a.phase==='Held'||a.phase==='Unshrink'||(a.phase==='Reach'&&model.o.sheathe))sword=compose(scaledGrip(model.setup,scale),pose[model.arm[2]]);
 return {...a,pose,scale,sword,holster:blendT(a.holster,b.holster,u),goal:blendT(a.goal,b.goal,u)};
}
function sampleBody(model,t){
 const f=sampleSource(model,recordedTime(model,t)),ret=model.fkReturn;
 if(!ret||t<ret.start)return f;
 const elapsed=t-ret.start,returnActive=elapsed<ret.timing.duration-1e-12,pose=elapsed===0?f.pose:Return.sample(ret,motion(model.data,model.o.motion,t),elapsed);
 const sword=model.o.sheathe?f.sword:compose(scaledGrip(model.setup,f.scale),pose[model.arm[2]]);
 const handError=len(sub(pose[model.arm[2]].p,f.goal.p));
 return {...f,pose,sword,handError,metrics:f.metrics?{...f.metrics,handError}:null,phase:returnActive?'FK return':f.phase,active:f.active||returnActive,fkReturn:{elapsed,duration:ret.timing.duration,active:returnActive}};
}
function sample(model,t){
 t=clamp(t,0,model.playbackDuration);
 const x=Math.min(t*60,model.headTrack.length-1),i=Math.floor(x),u=x-i;
 if(u<1e-10)return model.frames[i];
 const f=sampleBody(model,t),a=model.headTrack[i],b=model.headTrack[Math.min(i+1,model.headTrack.length-1)];
 const pose=Head.apply(model.headContext,f.pose,qslerp(a.q,b.q,u));
 return {...f,pose,headLook:a.info,active:f.active||!a.info.done};
}
const api={defaults,sanitize,prepare,sample,sampleBody,retime,recordedTime,motion,solve,compose,scaledGrip,seatHandAtScale,angle};if(typeof module!=='undefined')module.exports=api;else root.Holster=api;
})(globalThis);
