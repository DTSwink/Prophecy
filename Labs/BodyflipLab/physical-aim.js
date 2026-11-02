/* Predict the carrier turn, then steer the authored stroke as one chain. */
(function(root){
'use strict';
const node=typeof module!=='undefined',A=node?require('./attack-aim.js'):root.BodyflipAttackAim,P=node?require('./physical-flight.js'):root.BodyflipPhysicalFlight,R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,Work=node?require('./preparation.js'):root.BodyflipPreparation;
function create(rawSource,physicalOptions,{track,clip,settings,project=null,worldPose=p=>p}){
 const {names,parents,reference}=physicalOptions,start=physicalOptions.start??0,identity=p=>p,finish=project||identity,aim=settings.aim!==false,amount=1,undo=settings.undoRotation!==false,target=settings.target.slice(),hitTime=track.releaseTime??track.hitTime;
 const rig=M.model(names,parents,reference),rawCache=new Map(),originalSource=rawSource;
 rawSource=t=>{const key=Math.round(t*1e9);if(rawCache.has(key))return rawCache.get(key);const frame=originalSource(t);rawCache.set(key,frame);if(rawCache.size>1024)rawCache.delete(rawCache.keys().next().value);return frame;};
 const statistics={evaluations:0},neutral=P.create(rawSource,physicalOptions);
 let pikeJob=null,plan=null,physical=null,prediction=null,pending=null,best=null,previous=null,neutralHit=null,predictionTrack=neutral,throwAimOrigin=null;
 // A point-targeted spear must fit the final release after momentum response.
 // Rotating a predicted pose and then applying that world turn before the
 // carrier rotation is not equivalent: those two rotations do not commute.
 // Fit the same two spine angles against the actual trajectory instead.
 const pointThrow=track.isThrow&&track.kind==='spear'&&!track.throwDirection,candidates=new Map();let pointContext=null;
 function candidate(delta,context){
  const key=JSON.stringify(delta.throwAngles||delta.throwTurn||delta);if(candidates.has(key))return candidates.get(key);
  const moving=t=>{
   if(!delta.stroke)return delta;
   const span=hitTime-track.start-track.duration;
   // Preserve the outgoing steering velocity, then settle on the selected
   // heading when Undo rotation is off. Ordinary returns use their own fade.
   let time=t;
   if(!undo&&t>track.end){const d=track.returnEnd-track.end,u=Math.min(1,(t-track.end)/d);time=track.end+d*(u-u*u+u*u*u/3);}
   const u=(time-track.start-track.duration)/span,p=delta.stroke;
   const value=j=>{const a=p[j],b=4*p[j+2]-3*a-p[j+4],c=2*(a-2*p[j+2]+p[j+4]);return u<0?a+b*u:u>1?p[j+4]+(b+2*c)*(u-1):a+b*u+c*u*u;};
   return {...delta,heading:value(0),pitch:value(1)};
  };
  const pelvis=names.indexOf('pelvis'),basis=rawSource(hitTime).pose.q[pelvis],localYaw=t=>R.qm(R.qm(R.qinv(basis),context.deltaAt(moving(t),t).yaw),basis);
  // Air attack yaw is an intentional carrier turn, just like commanded spin.
  // Its angular velocity must enter the command budget; treating it as an
  // internal joint motion makes balance cancel the requested heading.
  const angularCommand=track.isThrow?null:(t,pose,dt)=>R.rotate(pose.q[pelvis],R.mul(R.qlog(R.qm(localYaw(t),R.qinv(localYaw(t-dt)))),1/dt));
  const source=t=>{const f=rawSource(t);if(!delta.stroke||context.weight(t,undo)<=0)return {...f,pose:finish(context.applyDeltaAt(f.pose,t,delta))};
   const turn=R.qm(f.spin?.rotation||[0,0,0,1],R.qinv(rawSource(hitTime).spin?.rotation||[0,0,0,1])),unspun=M.rotateAboutCOM(f.pose,R.qinv(turn),rig),posed=context.applyDeltaAt(unspun,t,moving(t));return {...f,pose:finish(M.rotateAboutCOM(posed,turn,rig))};};
  const path=P.create(source,{...physicalOptions,angularCommand});
  candidates.set(key,path);if(candidates.size>4)candidates.delete(candidates.keys().next().value);statistics.evaluations++;return path;
 }
 function preparePointThrow(){
  if(!plan){
   // Shaft fitting needs only the held transform, never release velocities.
   // Reading the sequence's carrier velocity while that sequence is being
   // prepared would recursively enter this same aim plan. The actual spawn
   // still computes its unchanged complete velocities after preparation.
   const sampleHit=t=>finish(worldPose(rawSource(t).pose,t)),launchAt=pose=>track.launchAt(pose,[0,0,0],[0,0,0]);
   neutralHit ||= neutral.sample(hitTime);
   const base=launchAt(sampleHit(hitTime)),carried=track.heldAt(finish(worldPose(neutralHit.pose,hitTime))),toward=R.unit(R.rotate(R.qinv(neutralHit.physical.rotation),R.sub(target,carried.p))),direction=R.unit(base.axis),yaw=Math.atan2(toward[0],toward[2])-Math.atan2(direction[0],direction[2]),seed=[Math.atan2(Math.sin(yaw),Math.cos(yaw)),Math.asin(direction[1])-Math.asin(toward[1])];
   plan=A.create({clip,track,names,parents,reference,sampleHit,launchAt,project,evaluationAmount:amount,evaluationUndoRotation:undo,
    evaluateMotion:(delta,context)=>{
     pointContext=context;const path=candidate(delta,context),sample=t=>finish(worldPose(path.sample(t).pose,t)),pose=sample(hitTime);
     return {pose,sample,launch:launchAt(pose)};
    // Conservation can make one heading branch unreachable. The opposite
    // winding is the same two-angle fit, without adding pelvis/arm freedom.
    },motionSolve:{throwSeeds:[seed,[seed[0]+(seed[0]<0?2:-2)*Math.PI,seed[1]]],iterations:24,maxStep:.6,tolerance:1e-7}});
  }
  const solved=plan.solution(target);physical=candidate(solved.state,pointContext);statistics.error=solved.error;candidates.clear();
 }
 // Reuse air-attack heading plus elevation in the predicted body frame.
 // The final compensated trajectory is the evaluator, so fitting and playback
 // cannot disagree about which direction the attack actually takes.
 function prepareMelee(){
  if(!plan){
   neutralHit ||= neutral.sample(hitTime);
   const hit=finish(worldPose(neutralHit.pose,hitTime)),probe=A.create({clip,track,names,parents,reference,sampleHit:()=>hit,project}),basis=R.qm(hit.q[names.indexOf('pelvis')],R.qinv(reference.q[names.indexOf('pelvis')])),ray=R.unit(R.rotate(R.qinv(basis),R.sub(probe.point(hit),M.center(hit,rig)))),goal=R.unit(R.rotate(R.qinv(basis),R.sub(target,M.center(hit,rig)))),difference=Math.atan2(goal[0],goal[2])-Math.atan2(ray[0],ray[2]),yaw=Math.atan2(Math.sin(difference),Math.cos(difference));

   plan=A.create({clip,track,names,parents,reference,sampleHit:t=>finish(worldPose(rawSource(t).pose,t)),project,evaluationAmount:amount,evaluationUndoRotation:undo,
    evaluateMotion:(delta,context)=>{pointContext=context;const path=candidate(delta,context);return {pose:finish(worldPose(path.sample(hitTime).pose,hitTime))};},
    motionSolve:{seed:[yaw,Math.asin(ray[1])-Math.asin(goal[1])],headingElevation:true,indices:[0,1],iterations:12,maxStep:1.2,tolerance:1e-6}});
  }
  const solved=plan.solution(target);physical=candidate(solved.state,pointContext);statistics.error=solved.error;candidates.clear();
 }
 // Pike aims the authored thrust at Armed, mid-stroke and Hit. Heading is
 // still a carrier command; elevation is still shared by the five spines.
 // The arm animation and free roll about the thrust direction remain intact.
 // One smooth angle curve is prepared ahead of playback, with the full
 // momentum response in each evaluation. There is no world-locked chest.
 function preparePike(){
  if(!pikeJob){
   prepareMelee();
   const armed=track.start+track.duration,mid=(armed+hitTime)/2,top=names.indexOf('spine_05'),base={...plan.solution(target).state},baseline=physical;
   const spinAt=t=>rawSource(t).spin?.rotation||[0,0,0,1],hitSpin=spinAt(hitTime);
   // With no carrier turn during the thrust, retain the accepted static aim.
   if([armed,mid].every(t=>R.length(R.qlog(R.qm(spinAt(t),R.qinv(hitSpin))))<1e-8))return;
   base.heading=Math.atan2(Math.sin(base.heading),Math.cos(base.heading));
   const rawHit=rawSource(hitTime),hitRay=R.rotate(R.qinv(hitSpin),R.sub(plan.point(rawHit.pose),M.center(rawHit.pose,rig))),times=[armed,mid,hitTime];
   const tops=times.map(t=>{const f=rawSource(t);return R.qm(R.qinv(spinAt(t)),f.pose.q[top]);});
   const evaluate=p=>{
    const path=candidate({...base,stroke:p},pointContext),residual=[];
    for(let i=0;i<times.length;i++){
     const t=times[i],pose=finish(worldPose(path.sample(t).pose,t)),center=M.center(pose,rig);
     // Before impact, preserve the source's changing arm pose and aim its
     // eventual thrust direction. The retracted tip is not the hit point.
     const ray=i===2?R.unit(R.sub(plan.point(pose),center)):R.unit(R.rotate(R.qm(pose.q[top],R.qinv(tops[i])),hitRay));
     residual.push(...R.sub(ray,R.unit(R.sub(target,center))));
    }
    return {path,residual};
   };
   const solve=(matrix,rhs)=>{
    const a=matrix.map((row,i)=>[...row,rhs[i]]),n=rhs.length;
    for(let i=0;i<n;i++){
     let k=i;for(let j=i+1;j<n;j++)if(Math.abs(a[j][i])>Math.abs(a[k][i]))k=j;
     [a[i],a[k]]=[a[k],a[i]];const d=a[i][i];if(Math.abs(d)<1e-15)return rhs.map(()=>0);
     for(let j=i;j<=n;j++)a[i][j]/=d;
     for(let k=0;k<n;k++)if(k!==i){const d=a[k][i];for(let j=i;j<=n;j++)a[k][j]-=d*a[i][j];}
    }
    return a.map(row=>row[n]);
   };
   function* fit(){
    let best=null;
    // The predicted-frame seed handles rear targets whose entry follows a
    // different heading branch from the final contact. No extra body roll.
    const aimBasis=R.qm(rawHit.pose.q[names.indexOf('pelvis')],R.qinv(reference.q[names.indexOf('pelvis')]));
    for(const predicted of [false,true]){
     let prior=base.heading;
     let p=times.flatMap(t=>{
      if(!predicted)return [base.heading,base.pitch];
      const spin=spinAt(t),frame=baseline.sample(t),basis=R.qm(R.qm(spin,R.qinv(hitSpin)),aimBasis),ray=R.unit(R.rotate(R.qinv(basis),R.rotate(spin,hitRay))),goal=R.unit(R.rotate(R.qinv(R.qm(frame.physical.rotation,basis)),R.sub(target,M.center(frame.pose,rig))));
      let yaw=Math.atan2(goal[0],goal[2])-Math.atan2(ray[0],ray[2]);yaw+=2*Math.PI*Math.round((prior-yaw)/(2*Math.PI));prior=yaw;
      return [yaw,Math.asin(ray[1])-Math.asin(goal[1])];
     });
     let value=yield p,error=R.length(value.residual);
     for(let n=0;n<24&&error>1e-6;n++){
      const h=1e-3,columns=[];
      for(let i=0;i<p.length;i++){const v=p.slice();v[i]+=h;const probe=yield v;columns.push(R.mul(R.sub(probe.residual,value.residual),1/h));}
      const damping=1e-5*Math.max(1,...columns.map(c=>R.dot(c,c))),matrix=columns.map((a,i)=>columns.map((b,j)=>R.dot(a,b)+(i===j?damping:0)));
      let step=solve(matrix,columns.map(c=>-R.dot(c,value.residual))),size=R.length(step);if(size>.8)step=R.mul(step,.8/size);
      let accepted=false;
      for(let scale=1;scale>=1/32;scale*=.5){const next=p.map((v,i)=>v+step[i]*scale);if(Math.abs(next[0])>Math.PI)continue;const candidate=yield next,e=R.length(candidate.residual);if(e<error){p=next;value=candidate;error=e;accepted=true;break;}}
      if(!accepted)break;
     }
     if(!best||error<best.error)best={...value,p,error};if(error<=1e-6)break;
    }
    return best;
   }
   // Keep preparation resumable. A target edit must not block the UI while
   // planning, or lose a completed trial when the shared work budget yields.
   pikeJob={iterator:fit(),evaluate,step:null,value:undefined,baseline,baselineError:statistics.error};physical=null;
  }
  for(;;){
   pikeJob.step ||= pikeJob.iterator.next(pikeJob.value);
   if(pikeJob.step.done){
    const solved=pikeJob.step.value,accepted=solved.error<1e-5;
    physical=accepted?solved.path:pikeJob.baseline;
    statistics.error=accepted?R.length(solved.residual.slice(6)):pikeJob.baselineError;
    statistics.pikeRejected=!accepted;statistics.strokeError=R.length(solved.residual.slice(0,6));statistics.strokeAngles=accepted?solved.p.map(v=>v*180/Math.PI):null;
    candidates.clear();pikeJob=null;return;
   }
   pikeJob.value=pikeJob.evaluate(pikeJob.step.value);pikeJob.step=null;Work.checkpoint();
  }
 }
 // Kick shape and its balanced motion stay intact. Aim is an explicit rigid
 // command, separate from internal articulation, as with the accepted sweep.
 function prepareKick(){
  const sampleHit=t=>finish(worldPose(neutral.sample(t).pose,t));
  plan=A.create({clip,track,names,parents,reference,sampleHit,project});
  const solved=plan.solution(target);statistics.evaluations=1;statistics.error=solved.error;
  const H=node?require('./momentum.js'):root.BodyflipMomentum,dt=1/240;
  physical={sample(t){
   const frame=neutral.sample(t),sweep=track.sweepPlane;
   if(t<=start||(!sweep&&(t<=track.start||t-start<1e-10))||(undo&&t>=(sweep?track.aimRecoveryEnd:track.returnEnd)))return frame;
   // Match the neutral integrator's actual interval, including fractional seeks.
   const tickTime=start+Math.floor((t-start)/neutral.step+1e-9)*neutral.step;
   const priorTime=sweep?Math.max(start,t-dt):Math.max(start,t-tickTime<1e-10?tickTime-neutral.step:tickTime);
   const delta=plan.rotation(t,target,amount,undo),q=delta.yaw,pose=plan.applyRotation(frame.pose,delta),before=neutral.sample(priorTime),elapsed=t-priorTime,prior=plan.rotation(priorTime,target,amount,undo),previous=plan.applyRotation(before.pose,prior);
   const omega=R.mul(R.qlog(R.qm(q,R.qinv(prior.yaw))),1/elapsed),momentum=H.momentum(previous,pose,rig,elapsed);
   let steering;
   if(!sweep){
    // Isolate the finite-step momentum from the prescribed aim turn. With
    // both endpoints at the same aim orientation this term is zero. Preserve
    // the neutral solver's residual instead of declaring measured motion exact.
    const heldPrevious=M.rotateAboutCOM(before.pose,q,rig);
    steering=R.sub(momentum,H.momentum(heldPrevious,pose,rig,elapsed));
   }else steering=M.product(M.tensor(pose,rig),omega);
   const command=R.add(R.rotate(q,frame.physical.target),steering),residual=R.sub(momentum,command),axis=frame.physical.axis&&R.rotate(q,frame.physical.axis);
   const carrier=frame.spin&&R.qm(q,frame.spin.rotation),spin=frame.spin?{...frame.spin,q:R.qm(q,frame.spin.q),rotation:carrier,omega:sweep?R.add(R.rotate(q,frame.spin.omega),omega):R.mul(R.qlog(R.qm(carrier,R.qinv(R.qm(prior.yaw,before.spin?.rotation||[0,0,0,1])))),1/elapsed)}:frame.spin;
   return {...frame,pose,spin,physical:{...frame.physical,rotation:R.qm(q,frame.physical.rotation),momentum,target:command,axis,error:axis?Math.abs(R.dot(residual,axis)):R.length(residual),fullResidual:R.length(residual),aimCommand:omega,...(!sweep?{aimMomentum:steering}:{})}};
  }};
 }
 function prepare(){
  if(physical)return;
  if(!aim||amount<=0){physical=neutral;return;}
  if(pointThrow){preparePointThrow();return;}
  if(track.fullBodyKick){prepareKick();return;}
  if(!track.isThrow){if(settings.pikeSpineAbsorb&&clip?.meta.name==='pike')preparePike();else prepareMelee();return;}
  if(track.isThrow&&!throwAimOrigin){const time=Number.isFinite(track.aimReferenceTime)?track.aimReferenceTime:track.start;throwAimOrigin=worldPose(rawSource(time).pose,time).points[names.indexOf('pelvis')].slice();}
  neutralHit ||= neutral.sample(hitTime);
  prediction ||= neutralHit.physical.rotation;
  while(statistics.evaluations<6){
   if(!pending){
    const turn=prediction.slice(),carrier=predictionTrack,carrierHit=carrier.sample(hitTime).physical.rotation,predicted=t=>{
     const correction=track.launchAt?R.qm(R.qm(carrier.sample(t).physical.rotation,R.qinv(carrierHit)),turn):turn;
     const base=rawSource(t).pose,p=M.rotateAboutCOM(base,correction,rig),center=neutral.sample(t).physical.com,shift=R.sub(center,M.center(p,rig));
     return finish(worldPose({...p,points:p.points.map(v=>R.add(v,shift))},t));
    },hit=predicted(hitTime);
    // The predictor owns this carrier sample; querying the outer sequence here
    // would recursively request the plan currently being prepared.
    const launchAt=track.launchAt?(pose,transform=identity)=>{const sample=t=>transform(predicted(t),t);return track.launchAt(pose,track.releaseVelocity(sample,undefined,predicted),track.projectileAngularVelocity(sample));}:null;
    const neutralPlan=A.create({clip,track,names,parents,reference,sampleHit:predicted,launchAt,project,throwAimOrigin,evaluateMotion:()=>({pose:hit}),motionSolve:{seed:[0,0,0,0,0,0],iterations:0}});
    const basis=R.qm(hit.q[names.indexOf('pelvis')],R.qinv(reference.q[names.indexOf('pelvis')])),world=A.between(neutralPlan.direction,neutralPlan.throwDirectionFor?.(target)||R.sub(target,neutralPlan.origin),R.rotate(basis,[0,1,0])),local=R.qm(R.qm(R.qinv(basis),world),basis),twist=R.unit([0,local[1],0,local[3]]),swing=R.qlog(R.qm(local,R.qinv(twist))),yaw=R.qlog(twist)[1];
    const candidatePlan=A.create({clip,track,names,parents,reference,sampleHit:predicted,launchAt,project,throwAimOrigin,evaluationAmount:amount,evaluationUndoRotation:undo,
     evaluateMotion:(delta,context)=>{const sample=t=>finish(context.applyDeltaAt(predicted(t),t,delta));return {pose:sample(hitTime),sample};},
     motionSolve:{seed:[yaw,swing[0],swing[2],0,0,0],iterations:18,maxStep:.6,indices:[0,1,2,3,4,5],scales:[1,1,1,.25,.25,1]}});
    pending={turn,plan:candidatePlan,track:null};
   }
   const attempt=pending;attempt.plan.correction(target);
   attempt.track ||= P.create(t=>{const f=rawSource(t);return {...f,pose:finish(attempt.plan.apply(f.pose,t,target,amount,undo))};},physicalOptions);
   const frame=attempt.track.sample(hitTime),pose=finish(worldPose(frame.pose,hitTime)),base=finish(worldPose(neutralHit.pose,hitTime));
   const launch=(physical,p)=>{const sample=t=>finish(worldPose(physical.sample(t).pose,t));return track.launchAt(p,track.releaseVelocity(sample,undefined,sample),track.projectileAngularVelocity?.(sample)||[0,0,0]);};
   const packet=track.launchAt?launch(attempt.track,pose):null,basePacket=track.launchAt?launch(neutral,base):null;
   const aimed=packet?A.launchAim(packet,target,attempt.plan.throwDirectionFor?.(target)):null,origin=aimed?aimed.origin:M.center(pose,rig),ray=R.unit(aimed?aimed.direction:R.sub(attempt.plan.point(pose),origin)),baseRay=R.unit(basePacket?A.launchAim(basePacket).direction:R.sub(attempt.plan.point(base),M.center(base,rig))),goal=R.rotate(R.qslerp([0,0,0,1],A.between(baseRay,aimed?aimed.wanted:R.sub(target,origin),[0,1,0]),amount),baseRay);
   const error=R.length(R.sub(ray,goal));statistics.evaluations++;
   if(!best||error<best.error)best={...attempt,error};
   const residual=R.qlog(R.qm(frame.physical.rotation,R.qinv(attempt.turn))),axis=frame.physical.axis;
   if(error<1e-4)break;
   let step=R.mul(residual,.6);
   // Axis balance leaves one scalar prediction to reconcile. A secant update
   // uses the last two completed flights instead of dozens of pose derivatives.
   if(axis&&previous){
    const change=R.dot(R.qlog(R.qm(attempt.turn,R.qinv(previous.turn))),axis),value=R.dot(residual,axis),old=R.dot(previous.residual,axis),slope=(value-old)/(change||1e-12);
    if(Math.abs(change)>1e-5&&Math.abs(slope)>.15)step=R.mul(axis,Math.max(-.8,Math.min(.8,-value/slope)));
   }
   previous={turn:attempt.turn,residual};predictionTrack=attempt.track;prediction=R.qm(R.qexp(step),attempt.turn);pending=null;Work.checkpoint();
  }
  plan=best.plan;physical=best.track;statistics.error=best.error;pending=null;
 }
 function sample(t){if(t<start)return rawSource(t);prepare();return {...physical.sample(t),physicalAim:true};}
 return {sample,prepare,statistics,get plan(){prepare();return plan;},get physical(){prepare();return physical;}};
}
const api={create};if(node)module.exports=api;else root.BodyflipPhysicalAim=api;
})(globalThis);
