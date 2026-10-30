/* Host-only continuous wall-slide arms. Feet/root remain owned by surface.js. */
(function(root){
'use strict';
const R=typeof module==='object'&&module.exports?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R,IDENT=[0,0,0,1];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const tangent=(v,n)=>sub(v,mul(n,dot(v,n)));
const copy=p=>({...p,points:p.points.slice(),q:p.q.slice(),axes:p.axes?.slice()});
function create({names,parents,joints,referenceLocal}){
 const ref=joints.reference;
 const arms=['l','r'].map(side=>{
  const a=names.indexOf('upperarm_'+side),b=names.indexOf('lowerarm_'+side),c=names.indexOf('hand_'+side),inverse=qinv(ref.q[parents[a]]),axis=unit(sub(ref.points[c],ref.points[a])),elbow=sub(ref.points[b],ref.points[a]);
  const other=names.indexOf('upperarm_'+(side==='l'?'r':'l'));
  return {side,a,b,c,sign:side==='l'?1:-1,axis:rotate(inverse,axis),pole:rotate(inverse,unit(tangent(elbow,axis))),outward:rotate(inverse,unit(sub(ref.points[a],ref.points[other]))),weight:null,weightVelocity:0,previous:null};
 });
 let preferred=null,previousHeading=null,previousTurnSpeed=null;
 const palmOffset=(q,sign)=>add(mul(rotate(q,[sign,0,0]),.0725),mul(rotate(q,[0,1,0]),sign===1?.020:-.025));
 function legalLocal(p,arm){
  const local=R.localize(p.points,p.q,parents);
  for(const j of [arm.a,arm.b,arm.c])local.q[j]=joints.project(j,IDENT,local.q[j],false).q;
  return local;
 }
 // Only this arm changed. Avoid localizing/rebuilding the entire skeleton
 // on every reach-fit iteration; retain the same constraint/FK arithmetic.
 function legalArm(p,a){
  const q=[],world=[],points=[];
  for(const j of[a.a,a.b,a.c])q[j]=joints.project(j,IDENT,unit(qm(qinv(p.q[parents[j]]),p.q[j])),false).q;
  const lowerOffset=rotate(qinv(p.q[a.a]),sub(p.points[a.b],p.points[a.a]));
  const handOffset=rotate(qinv(p.q[a.b]),sub(p.points[a.c],p.points[a.b]));
  world[a.a]=unit(qm(p.q[parents[a.a]],q[a.a]));
  world[a.b]=unit(qm(world[a.a],q[a.b]));
  world[a.c]=unit(qm(world[a.b],q[a.c]));
  points[a.b]=add(p.points[a.a],rotate(world[a.a],lowerOffset));
  points[a.c]=add(points[a.b],rotate(world[a.b],handOffset));
  return {local:{q},pose:{points,q:world}};
 }
 function step({pose,normal:n,up=[0,1,0],side,forward,plane,elapsed,dt,velocity,handShift=[0,0,0],frictionOffset=[0,0,0],freeOffset=[0,0,0],balanceTime=t=>t}){
  const wallUp=unit(tangent(up,n)),facing=dot(unit(tangent(forward,up)),mul(n,-1));
  const front=smooth((facing-.05)/.75),distances=arms.map(a=>dot(sub(pose.points[a.a],plane.project(pose.points[a.a])),n));
  if(preferred===null)preferred=distances[0]<=distances[1]?1:-1;
  // Nearer shoulder owns the side/back brace. The mild tie preference only
  // resolves exact back symmetry; it fades smoothly as front contact takes over.
  const nearL=smooth(.5+(distances[1]-distances[0]+preferred*.055*(1-front))/.10);
  const heading=unit(tangent(forward,up)),turnSpeed=previousHeading&&dt>0?Math.acos(clamp(dot(heading,previousHeading),-1,1))/dt:0;
  // Retain hand velocity across abrupt root yaw-window boundaries.
  if(previousTurnSpeed!==null&&dt>0&&Math.abs(turnSpeed-previousTurnSpeed)>60*dt)
   for(const a of arms)if(a.wallContact){a.turnRecovery=true;a.turnSettled=0;}
  previousTurnSpeed=turnSpeed;
  previousHeading=heading;
  const local=R.localize(pose.points,pose.q,parents),receipts=[];
  for(let index=0;index<arms.length;index++){
   const a=arms[index],parentQ=pose.q[parents[a.a]],shoulder=pose.points[a.a],l1=length(sub(pose.points[a.b],shoulder)),l2=length(sub(pose.points[a.c],pose.points[a.b])),reach=l1+l2;
   const neutralAxis=rotate(parentQ,a.axis),outward=rotate(parentQ,a.outward),restDirection=unit(add(add(mul(neutralAxis,.65),mul(up,-.35)),mul(outward,.16)));
   const orbitSide=unit(tangent(outward,restDirection)),orbitForward=unit(cross(orbitSide,restDirection));
   const orbitTime=balanceTime(elapsed),phase=orbitTime*(2*Math.PI*.55)+.18*Math.sin(orbitTime*1.1)+index*.35,ramp=clamp(elapsed/.7,0,1),envelope=ramp*ramp*ramp*(10+ramp*(-15+6*ramp));
   const circle=mul(add(mul(orbitSide,.07*Math.cos(phase)),mul(orbitForward,.10*Math.sin(phase))),envelope);
   const free=add(add(mul(restDirection,reach*(.93-.015*envelope*Math.sin(phase))),circle),freeOffset),distance=length(free),margin=reach*.06;
   const softReach=reach*.97-margin*Math.log1p(Math.exp((reach*.97-distance)/margin));
   const freeTarget=add(shoulder,mul(unit(free),Math.max(0,softReach))),freePole=rotate(R.fromTo(neutralAxis,unit(free)),rotate(parentQ,a.pole));
   const relaxed=joints.solveArm(copy(pose),a.side,freeTarget,freePole);
   const finger=wallUp,palmAxis=mul(n,-a.sign),handQ=R.fromAxes([mul(finger,a.sign),palmAxis,cross(mul(finger,a.sign),palmAxis)]);
   // Front support is shoulder-height and slightly spread; side/back reaches
   // remain lower so they don't force a backward shoulder extension.
   const lateral=tangent(outward,n),base=add(add(plane.project(shoulder),mul(unit(lateral),.10+.06*front)),mul(wallUp,-.08+.15*front));
   const requestedPoint=plane.closest(add(add(base,handShift),frictionOffset));
   const nearest=plane.closest(shoulder),shoulderOut=unit(add(mul(outward,.7),mul(wallUp,-.5)));
   function fit(t,orientation=handQ){
    const point=add(nearest,mul(sub(requestedPoint,nearest),t));
    let wrist=sub(point,palmOffset(orientation,a.sign)),braced,valid,armLocal;
    for(let k=0;k<24;k++){
     const off=sub(wrist,shoulder),d=length(off),m=reach*.01,max=reach*.996,x=(max-d)/m,safe=max-m*(Math.max(x,0)+Math.log1p(Math.exp(-Math.abs(x))));
     // Transport the accepted brace's bend direction to the new reach axis.
     // A small anatomical bias keeps it natural without repeatedly selecting
     // a distant shoulder-twist branch while the body turns.
     const axis=unit(off),authored=unit(tangent(add(mul(n,.65),shoulderOut),axis));
     const prior=a.bracePole?rotate(R.fromTo(a.braceAxis,axis),a.bracePole):authored;
     const pole=unit(tangent(add(mul(prior,.98),mul(authored,.02)),axis));
     braced=joints.solveArm(copy(pose),a.side,add(shoulder,mul(axis,Math.max(0,safe))),pole,orientation);
     const solved=legalArm(braced,a);armLocal=solved.local;valid=solved.pose;
     const palm=add(valid.points[a.c],palmOffset(valid.q[a.c],a.sign)),error=sub(point,palm);
     if(length(error)<.0003)break;
     // Fit against the actually constrained wrist and shoulder, not the
     // unconstrained request that may no longer have the same palm offset.
     const next=add(wrist,mul(error,.35));if(length(sub(next,wrist))<1e-7)break;wrist=next;
    }
    // Plane distance alone accepted palms that missed the requested target
    // sideways by14cm. Reach fitting must measure the full point error.
    const palm=add(valid.points[a.c],palmOffset(valid.q[a.c],a.sign)),gap=length(sub(palm,point));
    return {point,local:armLocal,gap,valid};
   }
   let best=fit(1);
   if(best.gap>.003){
    const neutral=fit(0);
    if(neutral.gap<best.gap){
     best=neutral;
     if(neutral.gap<.003){let lo=0,hi=1;for(let k=0;k<9;k++){const t=(lo+hi)*.5,candidate=fit(t);if(candidate.gap<.003){lo=t;best=candidate;}else hi=t;}}
    }
   }
   if(best.gap>.003){
    // A heel/palm-edge brace can remain reachable when a flush upright palm
    // cannot. Let the constrained wrist tilt, without moving the shoulder.
    for(const amount of [.4,.8,1.5,3]){
     const fingerTilt=unit(sub(wallUp,mul(n,amount))),palmTilt=unit(tangent(mul(n,-a.sign),fingerTilt));
     const orientation=R.fromAxes([mul(fingerTilt,a.sign),palmTilt,cross(mul(fingerTilt,a.sign),palmTilt)]),candidate=fit(0,orientation);
     if(candidate.gap<best.gap)best=candidate;
    }
   }
   // Commit history only after choosing a fit; trial candidates must not
   // steer the next frame's elbow pole.
   if(best.valid){
    const axis=unit(sub(best.valid.points[a.c],shoulder)),elbow=sub(best.valid.points[a.b],shoulder);
    a.bracePole=unit(tangent(elbow,axis));a.braceAxis=axis;
   }
   const point=best.point,braceLocal=best.local,freeLocal=legalLocal(relaxed,a),gap=best.gap;
   const sideWeight=smooth(2*(index?1-nearL:nearL)),reachWeight=1-smooth(Math.max(0,gap-.015)/.16),requested=(front+(1-front)*sideWeight)*reachWeight;
   if(a.weight===null)a.weight=requested;
   // Critically damped contact change: 0.3s settling rather than switching arms
   // at the front/back bisector or injecting an elbow branch discontinuity.
   const h=Math.max(0,dt),frequency=16;
   a.weightVelocity+=(frequency*frequency*(requested-a.weight)-2*frequency*a.weightVelocity)*h;
   a.weight=clamp(a.weight+a.weightVelocity*h,0,1);
   const goalQ={};
   for(const j of[a.a,a.b,a.c])goalQ[j]=joints.blendLocal(j,freeLocal.q[j],braceLocal.q[j],a.weight);
   // Keep the 24/s response for small contact chatter. A deliberate heading
   // change needs faster pursuit: angular speed * arm reach estimates target
   // speed, and dividing by 2mm bounds the intended tracking lag. This is a
   // kinematic response, not an additional Jolt force or joint limit.
   let response=1-Math.exp(-h*(24+turnSpeed*reach/.002));
   if(a.previous&&h>0){
    const maxStep=Math.max(...[a.a,a.b,a.c].map(j=>length(R.qlog(qm(goalQ[j],qinv(a.previous[j]))))));
    response=Math.min(response,h*6/Math.max(maxStep,1e-8));
   }
   for(const j of[a.a,a.b,a.c]){
    let q=goalQ[j];
    // One amount for the whole chain retains the solved arm's coordination.
    // Independent joint caps broke it; an uncapped response could still chase
    // an opposite twist-limit solution by tens of degrees in a single tick.
    if(a.previous&&h>0)q=joints.blendLocal(j,a.previous[j],q,response);
    local.q[j]=q;
   }
   a.previous={};for(const j of[a.a,a.b,a.c])a.previous[j]=local.q[j].slice();
   receipts.push({side:a.side,point,weight:a.weight});
  }
  const result=R.fk(local,parents);
  for(const r of receipts){const a=arms.find(a=>a.side===r.side),palm=add(result.points[a.c],palmOffset(result.q[a.c],a.sign));r.gap=length(sub(palm,plane.closest(palm)));r.touching=r.weight>.9&&r.gap<.004;}
  const hand=receipts.reduce((a,b)=>a.weight>=b.weight?a:b);
  return {pose:result,hands:receipts,hand};
 }
 // Clearance acts on the displayed chain after its entry/contact blends.
 // Keep the renderer's capsule radii and hand-box extents, not just the palm.
 function clear(pose,plane,dt){
  const n=plane.normal,local=R.localize(pose.points,pose.q,parents);
  for(const a of arms){
   const original=[a.a,a.b,a.c].map(j=>local.q[j]),parent=pose.q[parents[a.a]],shoulder=pose.points[a.a];
   const evaluate=qs=>{
    const qa=qm(parent,qs[0]),pb=add(shoulder,rotate(qa,local.p[a.b])),qb=qm(qa,qs[1]),pc=add(pb,rotate(qb,local.p[a.c])),qc=qm(qb,qs[2]);
    const distance=p=>length(sub(plane.closest(p),plane.project(p)))>.15?Infinity:dot(sub(p,plane.project(p)),n);
    const x=rotate(qc,[a.sign,0,0]),y=rotate(qc,[0,1,0]),z=rotate(qc,[0,0,1]),center=add(add(pc,mul(x,.0725)),mul(y,-.0025));
    const gaps=[distance(pb)-.0588,distance(pc)-.0488,distance(center)-Math.abs(dot(n,x))*.0725-Math.abs(dot(n,z))*.045-Math.abs(dot(n,y))*.0225];
    const loss=gaps.reduce((v,g,i)=>v+Math.max(0,(i<2?.03:.002)-g)**2,0);
    return {loss,gaps};
   };
   if(!a.clearance&&evaluate(original).loss<1e-8){
    // Seed continuity while clear of the wall, before the first correction.
    if(a.clearPrevious&&dt>0)a.clearVelocity=original.map((q,i)=>mul(R.qlog(qm(q,qinv(a.clearPrevious[i]))),1/dt));
    a.clearPrevious=original.map(q=>q.slice());
    if(a.worldHand&&dt>0)a.handVelocity=mul(sub(pose.points[a.c],a.worldHand),1/dt);
    a.worldHand=pose.points[a.c].slice();continue;
   }
   if(!a.clearance){a.clearEngaging=true;a.clearSettled=0;}
   let qs=original.map((q,i)=>a.clearance?joints.project([a.a,a.b,a.c][i],IDENT,qm(qslerp(a.clearance[i],IDENT,1-Math.exp(-dt*3)),q),false).q:q);
   let current=evaluate(qs),angle=.025;
   for(let pass=0;pass<64&&current.loss>1e-8;pass++){
    let best=current,next=qs;
    // Follow the continuous clearance gradient before trying individual axes.
    // A winner-takes-all axis search can flip its chosen shoulder axis while
    // two wall constraints exchange priority, causing a sideways hand kick.
    const gradient=[[0,0,0],[0,0,0],[0,0,0]];
    for(let i=0;i<1;i++){
     const g=[];
     for(let axis=0;axis<3;axis++){
      const v=[0,0,0];v[axis]=.001;const plus=qs.slice(),minus=qs.slice();
      plus[i]=joints.project([a.a,a.b,a.c][i],IDENT,qm(R.qexp(v),qs[i]),false).q;
      minus[i]=joints.project([a.a,a.b,a.c][i],IDENT,qm(R.qexp(mul(v,-1)),qs[i]),false).q;
      g[axis]=(evaluate(plus).loss-evaluate(minus).loss)/.002;
     }
     gradient[i]=g;
    }
    const norm=Math.sqrt(gradient.reduce((sum,g)=>sum+dot(g,g),0));
    if(norm>1e-10){
     for(let scale=angle;scale>.0001;scale*=.5){
      const candidate=qs.map((q,i)=>joints.project([a.a,a.b,a.c][i],IDENT,qm(R.qexp(mul(gradient[i],-scale/norm)),q),false).q),score=evaluate(candidate);
      if(score.loss<best.loss-1e-12){best=score;next=candidate;break;}
     }
    }
    if(next===qs)
    for(let i=0;i<3;i++)for(let axis=0;axis<3;axis++)for(const sign of[-1,1]){
     const vector=[0,0,0];vector[axis]=sign*angle;const candidate=qs.slice();
     candidate[i]=joints.project([a.a,a.b,a.c][i],IDENT,qm(R.qexp(vector),qs[i]),false).q;
     const score=evaluate(candidate);if(score.loss<best.loss-1e-12){best=score;next=candidate;}
    }
    if(next===qs){angle*=.5;if(angle<.0005)break;}else {
     if(best.loss<1e-8){let lo=0,hi=1;for(let k=0;k<9;k++){const mid=(lo+hi)*.5,test=qs.map((q,i)=>joints.blendLocal([a.a,a.b,a.c][i],q,next[i],mid));if(evaluate(test).loss<1e-8)hi=mid;else lo=mid;}next=qs.map((q,i)=>joints.blendLocal([a.a,a.b,a.c][i],q,next[i],hi));best=evaluate(next);}
     qs=next;current=best;
    }
   }
   // Spend the clearance reserve on temporal continuity before allowing a
   // faster correction. Never smooth the displayed collider into the wall.
   if(a.clearPrevious&&dt>0){
    const indices=[a.a,a.b,a.c],maxStep=Math.max(...qs.map((q,i)=>length(R.qlog(qm(q,qinv(a.clearPrevious[i]))))));
    const amount=Math.min(1,dt*6/Math.max(maxStep,1e-8));
    const blend=t=>qs.map((q,i)=>joints.blendLocal(indices[i],a.clearPrevious[i],q,t));
    let candidate=blend(amount);
    // Entering clearance or releasing a brace can change the legal IK branch.
    // Bound the change of angular velocity, not only its magnitude, so those
    // switches do not instantly reverse the displayed arm. Wall safety below
    // can still override this when the actual collider would penetrate.
    if(a.clearVelocity&&(a.weightVelocity<0||a.clearEngaging)&&a.weight>.05){
     const wanted=candidate.map((q,i)=>mul(R.qlog(qm(q,qinv(a.clearPrevious[i]))),1/dt));
     const change=wanted.map((v,i)=>sub(v,a.clearVelocity[i]));
     // Fade the entry limiter as contact settles; retaining it through the
     // whole brace can store lag and force a later wall-safety snap.
     const entryWeight=a.clearEngaging&&a.weightVelocity>=0?smooth((.95-a.weight)/.1):1;
     const fraction=Math.min(1,dt*45/Math.max(1e-8,entryWeight*Math.max(...change.map(length))));
     if(a.clearEngaging&&a.weight>=.95)a.clearEngaging=false;
     if(a.clearEngaging){a.clearSettled=fraction===1?(a.clearSettled||0)+1:0;if(a.clearSettled>=4)a.clearEngaging=false;}
     candidate=candidate.map((q,i)=>joints.project(indices[i],IDENT,qm(R.qexp(mul(add(a.clearVelocity[i],mul(change[i],fraction)),dt)),a.clearPrevious[i]),false).q);
    }
    if(a.turnRecovery&&a.worldHand&&a.handVelocity){
     const armPose=q=>{const qa=qm(parent,q[0]),pb=add(shoulder,rotate(qa,local.p[a.b])),qb=qm(qa,q[1]),pc=add(pb,rotate(qb,local.p[a.c]));return {qa,pb,qb,pc,qc:qm(qb,q[2])};};
     const arm=armPose(candidate),wanted=mul(sub(arm.pc,a.worldHand),1/dt),change=sub(wanted,a.handVelocity);
     const amount=Math.min(1,15*dt/Math.max(1e-8,length(change)));
     a.turnSettled=amount===1?(a.turnSettled||0)+1:0;
     if(a.turnSettled>=4)a.turnRecovery=false;
     if(amount<1){
      const target=add(a.worldHand,mul(add(a.handVelocity,mul(change,amount)),dt));
      const trial=copy(pose);trial.points[a.b]=arm.pb;trial.points[a.c]=arm.pc;trial.q[a.a]=arm.qa;trial.q[a.b]=arm.qb;trial.q[a.c]=arm.qc;
      const pole=unit(tangent(sub(arm.pb,shoulder),unit(sub(arm.pc,shoulder))));
      const solved=legalArm(joints.solveArm(trial,a.side,target,pole,arm.qc),a);
      candidate=indices.map(j=>solved.local.q[j]);
     }
    }
    if(evaluate(candidate).gaps.some(g=>g<.0003)){
     const predicted=candidate,repair=t=>qs.map((q,i)=>joints.blendLocal(indices[i],predicted[i],q,t));
     let lo=0,hi=1;for(let k=0;k<10;k++){const mid=(lo+hi)*.5;if(evaluate(repair(mid)).gaps.some(g=>g<.0003))lo=mid;else hi=mid;}candidate=repair(hi);
    }
    qs=candidate;
   }
   if(a.clearPrevious&&dt>0)a.clearVelocity=qs.map((q,i)=>mul(R.qlog(qm(q,qinv(a.clearPrevious[i]))),1/dt));
   const qa=qm(parent,qs[0]),pb=add(shoulder,rotate(qa,local.p[a.b])),pc=add(pb,rotate(qm(qa,qs[1]),local.p[a.c]));
   if(a.worldHand&&dt>0)a.handVelocity=mul(sub(pc,a.worldHand),1/dt);
   a.worldHand=pc;
   a.clearPrevious=qs.map(q=>q.slice());
   a.clearance=qs.map((q,i)=>qm(q,qinv(original[i])));
   a.wallContact=a.weight>.9&&evaluate(qs).gaps[2]<.004;
   for(let i=0;i<3;i++)local.q[[a.a,a.b,a.c][i]]=qs[i];
  }
  return R.fk(local,parents);
 }
 function contact(pose,side,plane){
  const a=arms.find(a=>a.side===side),q=pose.q[a.c],x=rotate(q,[a.sign,0,0]),y=rotate(q,[0,1,0]),z=rotate(q,[0,0,1]);
  let point=add(add(pose.points[a.c],mul(x,.0725)),mul(y,-.0025));
  for(const [axis,half] of[[x,.0725],[y,.0225],[z,.045]]){const d=dot(axis,plane.normal);if(Math.abs(d)>1e-5)point=add(point,mul(axis,-Math.sign(d)*half));}
  const target=plane.closest(point);return {point:target,gap:length(sub(point,target))};
 }
 return {step,clear,contact};
}
const api={create};if(typeof module==='object'&&module.exports)module.exports=api;else root.SlideArms=api;
})(typeof globalThis!=='undefined'?globalThis:this);

