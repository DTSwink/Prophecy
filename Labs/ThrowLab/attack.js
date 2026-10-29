(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length,unit,rotate,qm,qinv,qexp,localize,fk}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*x*(10+x*(-15+6*x));};
function rig(names,parents){
 const spines=[1,2,3,4,5].map(i=>names.indexOf('spine_0'+i)),pelvis=names.indexOf('pelvis');
 if(pelvis<0||spines.some(i=>i<0))throw Error('Throw attack modes require pelvis and spine_01 through spine_05');
 const upper=parents.map((_,j)=>{while(j>=0&&j!==spines[0])j=parents[j];return j===spines[0];});
 return {parents,pelvis,spines,upper,clavicles:new Set(['clavicle_l','clavicle_r'].map(n=>names.indexOf(n))),shoulder:names.indexOf('upperarm_l'),elbow:names.indexOf('lowerarm_l'),hand:names.indexOf('hand_l'),throwArm:new Set(['lowerarm_l','hand_l'].map(n=>names.indexOf(n)))};
}
function chargeTiming(armed,release,amount){
 amount=clamp(amount,0,1);const trigger=armed*amount;
 return {trigger,release:trigger+release-armed,forward:release-armed};
}
const armDirection=(pose,rig,j=rig.hand)=>unit(sub(pose.points[j],pose.points[rig.shoulder]));
function swingBasis(initial,release,rig){
 const neutral=armDirection(initial,rig),axis=unit(R.cross(neutral,armDirection(release,rig)));
 return {neutral,axis};
}
const swingAngle=(direction,basis)=>Math.atan2(dot(R.cross(basis.neutral,direction),basis.axis),dot(basis.neutral,direction));
function chargeCurve(sample,armed,release,end,rig){
 const basis=swingBasis(sample(0),sample(release),rig),samples=[];
 for(let f=0;f<end;f+=.25)samples.push({frame:f,angle:swingAngle(armDirection(sample(f),rig),basis)});
 samples.push({frame:end,angle:swingAngle(armDirection(sample(end),rig),basis)});
 let peak=samples.findIndex(s=>s.frame>=release);
 for(let i=peak;i<samples.length;i++)if(samples[i].angle>samples[peak].angle)peak=i;
 let back=samples.findIndex(s=>s.frame>=armed);
 for(let i=back;i<=peak;i++)if(samples[i].angle<samples[back].angle)back=i;
 const forward=[];
 for(let i=back;i<=peak;i++)if(!forward.length||samples[i].angle>forward.at(-1).angle)forward.push(samples[i]);
 return {armed,peak:samples[peak].frame,samples,forward};
}
function lookup(rows,value,key,result){
 if(value<=rows[0][key])return rows[0][result];
 if(value>=rows.at(-1)[key])return rows.at(-1)[result];
 let lo=0,hi=rows.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(rows[mid][key]<value)lo=mid;else hi=mid;}
 const a=rows[lo],b=rows[hi],t=(value-a[key])/(b[key]-a[key]);return a[result]+t*(b[result]-a[result]);
}
function chargeFrame(curve,amount,elapsed){
 if(amount===0)return 0;
 // Select the shorter source segment once conceptually, then advance through
 // it uniformly. Re-mapping every full-throw angle created an armed plateau
 // whenever an early charge pose was already close to neutral.
 const angle=f=>lookup(curve.samples,f,'frame','angle');
 const start=lookup(curve.forward,angle(curve.armed*amount),'angle','frame');
 const end=lookup(curve.forward,amount*angle(curve.peak),'angle','frame');
 const progress=clamp(elapsed/Math.max(1e-9,curve.peak-curve.armed),0,1);
 return start+(end-start)*progress;
}
function chargeSpeed(curve,amount,blend=0){
 if(amount<=0||amount>=1)return {baseRate:1,rate:1,multiplier:1};
 const span=curve.peak-curve.armed;
 const distance=chargeFrame(curve,amount,span)-chargeFrame(curve,amount,0);
 if(span<=1e-9||distance<=1e-9)return {baseRate:1,rate:1,multiplier:1};
 const baseRate=distance/span,rate=baseRate+(1-baseRate)*clamp(blend,0,1);
 return {baseRate,rate,multiplier:rate/baseRate};
}
function prepareBody({sample,rig,amount,trigger,returnFrame,end}){
 const effort=amount*amount;
 const neutral=localize(sample(0).points,sample(0).q,rig.parents);
 const at=sample(trigger),h=Math.min(1e-4,trigger),before=sample(trigger-h);
 const reached=localize(at.points,at.q,rig.parents),previous=localize(before.points,before.q,rig.parents);
 const delta=(local,j)=>R.qlog(qm(qinv(neutral.q[j]),local.q[j]));
 const rotation=reached.q.map((_,j)=>delta(reached,j));
 const velocity=rotation.map((q,j)=>mul(sub(q,delta(previous,j)),h>0?1/h:0));
 const translation=reached.p.map((p,j)=>sub(p,neutral.p[j]));
 const linear=reached.p.map((p,j)=>mul(sub(p,previous.p[j]),h>0?1/h:0));
 const settle=Math.min(4,Math.max(1e-9,(end-trigger)/3));
 const returnStart=clamp(returnFrame,trigger+settle,end-settle),returnEnd=end;
 const clavicleReturnEnd=clamp(returnFrame,trigger+2*settle,end);
 return {settle,returnStart,returnEnd,clavicleReturnEnd,local(source,frame){
  const local=localize(source.points,source.q,rig.parents);
  if(amount===1||frame<=trigger)return local;
  if(amount===0)return {p:neutral.p.map(p=>p.slice()),q:neutral.q.map(q=>q.slice())};
  // Scale only motion still to come. Fading the already-reached lean toward
  // neutral made the head move backward, then forward again during the throw.
  // Keep the torso's established timing. Only the clavicles unwind their
  // retained wind-up during the throw, instead of staying shrugged/turned.
  const u=clamp((frame-trigger)/settle,0,1),travel=settle*(u-2.5*u**4+3*u**5-u**6);
  const bodyResidual=(1-effort)*(1-smooth((frame-returnStart)/Math.max(1e-9,returnEnd-returnStart)));
  const clavicleResidual=(1-effort)*(1-smooth((frame-trigger)/Math.max(1e-9,clavicleReturnEnd-trigger)));
  for(let j=0;j<rig.parents.length;j++)if(j!==rig.shoulder&&!rig.throwArm.has(j)){
   const residual=rig.clavicles.has(j)?clavicleResidual:bodyResidual;
   local.q[j]=unit(qm(neutral.q[j],qexp(add(mul(delta(local,j),effort),mul(add(rotation[j],mul(velocity[j],travel)),residual)))));
   const len=length(local.p[j]),p=add(neutral.p[j],add(mul(sub(local.p[j],neutral.p[j]),effort),mul(add(translation[j],mul(linear[j],travel)),residual)));
   local.p[j]=rig.parents[j]<0||j===rig.pelvis?p:mul(unit(p),len);
  }
  return local;
 }};
}
function partialPose({source,charged,action,rig,amount,recover=0,entry=0,ending,anchor=source,body,frame,anchorFrame=frame}){
 if(amount===1)return source;
 const start=localize(charged.points,charged.q,rig.parents),motion=localize(action.points,action.q,rig.parents),end=localize(ending.points,ending.q,rig.parents),blend=smooth(entry);
 const isArm=j=>j===rig.shoulder||rig.throwArm.has(j);
 // Every body joint uses the same original timeline, including follow-through
 // and return. Only the throwing arm uses the shortened source-pose sequence.
 const local=body.local(anchor,anchorFrame);
 for(let j=0;j<rig.parents.length;j++)if(isArm(j)){
  const q=amount===0?start.q[j]:motion.q[j],p=amount===0?start.p[j]:motion.p[j];
  local.q[j]=R.qslerp(start.q[j],q,blend);
  local.p[j]=mul(unit(R.offsetBlend(start.p[j],p,blend)),length(local.p[j]));
 }
 if(amount>0){
  const pose=fk(local,rig.parents),j=rig.shoulder;
  local.q[j]=unit(qm(qinv(pose.q[rig.parents[j]]),R.qslerp(charged.q[j],action.q[j],blend)));
 }
 for(let j=0;j<rig.parents.length;j++)if(isArm(j)){
  local.q[j]=R.qslerp(local.q[j],end.q[j],recover);local.p[j]=R.offsetBlend(local.p[j],end.p[j],recover);
 }
 if(anchor!==source){
  const current=body.local(source,frame);
  for(let j=0;j<rig.parents.length;j++)if(!isArm(j)){local.q[j]=current.q[j];local.p[j]=current.p[j];}
 }
 return fk(local,rig.parents);
}
function prepareCarry({incoming,outgoing,rig,frame,duration}){
 const h=1e-4,at=incoming(frame),before=incoming(frame-h),after=outgoing(frame+h);
 const a=localize(at.points,at.q,rig.parents),b=localize(before.points,before.q,rig.parents),c=localize(after.points,after.q,rig.parents);
 const joints=[rig.shoulder,rig.elbow,rig.hand];
 const seeds=joints.map(j=>({j,
  angular:mul(sub(R.qlog(qm(qinv(b.q[j]),a.q[j])),R.qlog(qm(qinv(a.q[j]),c.q[j]))),1/h),
  offset:mul(sub(R.qlog(R.fromTo(b.p[j],a.p[j])),R.qlog(R.fromTo(a.p[j],c.p[j]))),1/h)
 }));
 return {rig,frame,duration,seeds};
}
function carryPose(pose,carry,frame){
 const elapsed=frame-carry.frame;if(elapsed<=0||elapsed>=carry.duration)return pose;
 const u=elapsed/carry.duration,momentum=carry.duration*(u-6*u**3+8*u**4-3*u**5);
 const local=localize(pose.points,pose.q,carry.rig.parents);
 // Finite FK follow-through: match the incoming velocity and smoothly remove
 // the correction, with zero value/velocity/acceleration at its endpoint.
 for(const {j,angular,offset} of carry.seeds){
  local.q[j]=unit(qm(local.q[j],qexp(mul(angular,momentum))));
  local.p[j]=rotate(qexp(mul(offset,momentum)),local.p[j]);
 }
 return fk(local,carry.rig.parents);
}
function halfPose(source,initial,rig){
 const local=localize(source.points,source.q,rig.parents),fixed=localize(initial.points,initial.q,rig.parents);
 for(let j=0;j<rig.parents.length;j++)if(!rig.upper[j]){local.p[j]=fixed.p[j];local.q[j]=fixed.q[j];}
 // Freeze the lower body but retain the complete authored world orientation
 // above the pelvis, including the user's hand/forearm edits.
 const first=rig.spines[0];local.q[first]=unit(qm(qinv(initial.q[rig.parents[first]]),source.q[first]));
 const result=fk(local,rig.parents);
 for(let j=0;j<rig.parents.length;j++)if(!rig.upper[j]){result.points[j]=initial.points[j].slice();result.q[j]=initial.q[j].slice();result.axes[j]=initial.axes[j];}
 return result;
}
function correction(yaw,pitch,heading){
 const yawQ=qexp([0,yaw,0]),right=[Math.cos(heading+yaw),0,-Math.sin(heading+yaw)];
 const pitchQ=qexp(mul(right,pitch));return {yawQ,pitchQ,right,rotation:unit(qm(pitchQ,yawQ))};
}
function turnPose(source,rig,initial,half,yaw,pitch,heading,weight=1){
 if(weight===0||(!yaw&&!pitch))return source;
 const local=localize(source.points,source.q,rig.parents),turn=correction(yaw*weight,pitch*weight,heading);
 const points=[],q=[],spineIndex=new Map(rig.spines.map((j,i)=>[j,i]));
 for(let j=0;j<rig.parents.length;j++){
  const parent=rig.parents[j];
  if(parent<0){points[j]=half?local.p[j]:add(initial.points[j],rotate(turn.yawQ,sub(local.p[j],initial.points[j])));q[j]=half?local.q[j]:unit(qm(turn.yawQ,local.q[j]));}
  else {points[j]=add(points[parent],rotate(q[parent],local.p[j]));q[j]=unit(qm(q[parent],local.q[j]));}
  if(spineIndex.has(j)){
   const amount=(spineIndex.get(j)+1)/rig.spines.length;
   // Share yaw and pitch continuously, including when facing behind. Taking
   // the shortest log of their combined quaternion would flip the spine bend
   // at 180 degrees and make some near-backward targets impossible to fit.
   const cumulative=qm(qexp(mul(turn.right,pitch*weight*amount)),half?qexp([0,yaw*weight*amount,0]):turn.yawQ);
   q[j]=unit(qm(cumulative,source.q[j]));
  }
 }
 return {points,q,axes:q.map(R.toAxes)};
}
function prepare({rig,initial,armedPose,releasePose,velocity,target,half=false,aim=false,armed=0,aimAxis=null,aimPoint=null,aimBone=null}){
 const base=half?halfPose(releasePose,initial,rig):releasePose,top=rig.spines.at(-1);
 const weaponAim=aimAxis&&aimPoint&&Number.isInteger(aimBone)&&aimBone>=0;
 const reference=weaponAim?aimAxis:velocity,direction=unit(reference),heading=Math.atan2(direction[0],direction[2]);
 const localPoint=weaponAim?rotate(qinv(releasePose.q[aimBone]),sub(aimPoint,releasePose.points[aimBone])):null;
 const origin=pose=>weaponAim?add(pose.points[aimBone],rotate(pose.q[aimBone],localPoint)):pose.points[top];
 let yaw=0,pitch=0,error=0,valid=aim&&length(reference)>1e-8&&length(sub(target,origin(base)))>1e-8;
 if(valid){
  const toward=unit(sub(target,origin(base))),targetHeading=Math.hypot(toward[0],toward[2])>1e-8?Math.atan2(toward[0],toward[2]):heading;
  yaw=Math.atan2(Math.sin(targetHeading-heading),Math.cos(targetHeading-heading));
  pitch=Math.asin(clamp(direction[1],-1,1))-Math.asin(clamp(toward[1],-1,1));
  // Articulation moves the held weapon's origin as well as its shaft axis.
  // Fit the forward shaft ray to the target, including the complete grip.
  // Bombs retain their original chest/velocity reference. Fit two angles once
  // per settings change, with no pelvis-pitch fallback or ballistic steering.
  const residual=(y,p)=>{
   const pose=turnPose(base,rig,initial,half,y,p,heading),to=sub(target,origin(pose));
   return sub(rotate(correction(y,p,heading).rotation,direction),unit(to));
  };
  let r=residual(yaw,pitch);
  for(let i=0;i<24&&length(r)>1e-9;i++){
   const h=1e-5,a=mul(sub(residual(yaw+h,pitch),r),1/h),b=mul(sub(residual(yaw,pitch+h),r),1/h);
   const aa=dot(a,a)+1e-6,ab=dot(a,b),bb=dot(b,b)+1e-6,ar=dot(a,r),br=dot(b,r),det=aa*bb-ab*ab;
   if(det<1e-14)break;
   let dy=(-bb*ar+ab*br)/det,dp=(ab*ar-aa*br)/det,limit=Math.max(1,Math.hypot(dy,dp)/.5);dy/=limit;dp/=limit;
   let accepted=false;
   for(let step=1;step>=1/64;step/=2){const next=residual(yaw+dy*step,pitch+dp*step);if(length(next)<length(r)){yaw+=dy*step;pitch+=dp*step;r=next;accepted=true;break;}}
   if(!accepted)break;
  }
  error=length(r);
 }
 const rotation=correction(yaw,pitch,heading).rotation;
 const startLocal=valid&&armedPose?localize(initial.points,initial.q,rig.parents):null;
 const armedLocal=startLocal?localize(armedPose.points,armedPose.q,rig.parents):null;
 return {rotation,yaw,pitch,error,valid,
  apply(source,frame){
   if(!half&&!valid)return source;
   // Direct FK entry into Armed. Apply hand/forearm editing after this layer
   // so whole-frame user keys remain editable even during the new wind-up.
   if(startLocal&&armed>0&&frame<armed){
    const u=smooth(frame/armed);
    source=fk({q:startLocal.q.map((q,j)=>R.qslerp(q,armedLocal.q[j],u)),p:startLocal.p.map((p,j)=>rig.parents[j]<0||j===rig.pelvis?add(p,mul(sub(armedLocal.p[j],p),u)):R.offsetBlend(p,armedLocal.p[j],u))},rig.parents);
   }
   const base=half?halfPose(source,initial,rig):source;
   return valid?turnPose(base,rig,initial,half,yaw,pitch,heading,armed>0?smooth(frame/armed):1):base;
  }
 };
}
const api={rig,chargeTiming,armDirection,swingBasis,swingAngle,chargeCurve,chargeFrame,chargeSpeed,prepareBody,partialPose,prepareCarry,carryPose,halfPose,turnPose,prepare};if(typeof module!=='undefined')module.exports=api;else root.ThrowAttack=api;
})(globalThis);
