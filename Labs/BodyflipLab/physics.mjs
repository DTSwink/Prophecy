import initJolt from './vendor/jolt.mjs';
export async function createPhysics(manifest,idle,{selfCollision=true}={}){
 const C=globalThis.BodyflipCore||(await import('./core.js')).default;
 const T=globalThis.BodyflipTorso||(await import('./torso.js')).default;
 const Target=globalThis.BodyflipTargetRig||(await import('./target-rig.js')).default;
 const M=globalThis.BodyflipMass||(await import('./mass.js')).default;
 const W=globalThis.BodyflipWrist||(await import('./wrist.js')).default;
 const J=await initJolt(),R=globalThis.Recovery,{sub,add,mul,length,unit,cross,dot,rotate,qm,qinv,fromTo}=R;
 const vec=a=>new J.Vec3(...a),pos=a=>new J.RVec3(...a),quat=a=>new J.Quat(...a),arr=v=>[v.GetX(),v.GetY(),v.GetZ()],qa=q=>[q.GetX(),q.GetY(),q.GetZ(),q.GetW()];
 const settings=new J.JoltSettings();settings.mMaxWorkerThreads=0;
 const filter=new J.ObjectLayerPairFilterTable(1);filter.EnableCollision(0,0);
 const bp=new J.BroadPhaseLayerInterfaceTable(1,1),layer=new J.BroadPhaseLayer(0);bp.MapObjectToBroadPhaseLayer(0,layer);J.destroy(layer);
 settings.mObjectLayerPairFilter=filter;settings.mBroadPhaseLayerInterface=bp;settings.mObjectVsBroadPhaseLayerFilter=new J.ObjectVsBroadPhaseLayerFilterTable(bp,1,filter,1);
 const world=new J.JoltInterface(settings);J.destroy(settings);const system=world.GetPhysicsSystem(),bi=system.GetBodyInterface(),zero=vec([0,0,0]);system.SetGravity(zero);
 const ps=system.GetPhysicsSettings();ps.mNumVelocitySteps=20;ps.mNumPositionSteps=8;system.SetPhysicsSettings(ps);
 const {names,parents}=manifest,targetRig=Target.create(names,parents,idle),torso=T.create(names,parents,idle),rig=M.model(names,parents,idle),rigByBone=new Map(rig.map(s=>[s.i,s])),torsoByBone=new Map(torso.map(s=>[s.bone,s])),bodies=[],joints=[],group=new J.GroupFilterTable(names.length);
 // Adjacent and overlapping torso volumes are excluded; separate limbs collide.
 const core=name=>/^(pelvis|spine|neck|head|clavicle)/.test(name);
 for(let a=1;a<names.length;a++)for(let b=a+1;b<names.length;b++){
  const near=parents[b]===a||parents[a]===b||parents[a]===parents[b]||parents[parents[b]]===a||parents[parents[a]]===b;
  const torso=core(names[a])&&core(names[b]);
  const shoulder=(core(names[a])&&names[b].startsWith('upperarm'))||(core(names[b])&&names[a].startsWith('upperarm'));
  if(!selfCollision||near||torso||shoulder)group.DisableCollision(a,b);
 }
 function radius(name){if(name==='pelvis')return .105;if(name.startsWith('spine'))return .08;if(name==='head')return .09;if(name.startsWith('thigh'))return .065;if(name.startsWith('calf'))return .045;return .032;}
 for(let i=1;i<names.length;i++){
  const child=parents.findIndex((p,j)=>p===i&&!names[j].startsWith('clavicle')&&!names[j].startsWith('thigh'));
  const delta=child>0?sub(idle.points[child],idle.points[i]):rotate(idle.q[i],[names[i]==='head'?.12:.045,0,0]),l=length(delta),r=radius(names[i]);
  const spec=rigByBone.get(i),spine=torsoByBone.get(i),off=vec(spec.offset),rot=quat(spec.rotation);
  const half=spine?vec(mul(spine.dims,.5)):null,shapeSettings=spine?new J.BoxShapeSettings(half,0):new J.CapsuleShapeSettings(spec.halfHeight,spec.radius),compound=new J.RotatedTranslatedShapeSettings(off,rot,shapeSettings),result=compound.Create(),shape=result.Get();
  const p=pos(idle.points[i]),q=quat(idle.q[i]),creation=new J.BodyCreationSettings(shape,p,q,i===1?J.EMotionType_Kinematic:J.EMotionType_Dynamic,0);
  creation.mAllowDynamicOrKinematic=true;creation.mAllowSleeping=false;creation.mLinearDamping=.05;creation.mAngularDamping=.05;creation.mMaxAngularVelocity=1000;creation.mMaxLinearVelocity=1000;
  creation.mOverrideMassProperties=J.EOverrideMassProperties_CalculateInertia;creation.mMassPropertiesOverride.mMass=spec.mass;
  creation.mCollisionGroup.SetGroupFilter(group);creation.mCollisionGroup.SetGroupID(1);creation.mCollisionGroup.SetSubGroupID(i);
  bodies[i]=bi.CreateBody(creation);bi.AddBody(bodies[i].GetID(),J.EActivation_Activate);
  for(const v of [creation,p,q,compound,result,off,rot])J.destroy(v);if(half)J.destroy(half);
 }
 function motor(m){m.mSpringSettings.mMode=J.ESpringMode_FrequencyAndDamping;m.mSpringSettings.mFrequency=50;m.mSpringSettings.mDamping=1;m.mMinTorqueLimit=-2000;m.mMaxTorqueLimit=2000;}
 for(let i=2;i<names.length;i++){
  const parent=parents[i],hinge=/^(calf|lowerarm)_/.test(names[i]),cfg=hinge?new J.HingeConstraintSettings():new J.SwingTwistConstraintSettings(),anchor=pos(idle.points[i]);
  cfg.mNumVelocityStepsOverride=24;cfg.mNumPositionStepsOverride=10;
  let axis,normal,lo=0,hi=0;
  if(hinge){
   const definition=targetRig.joints.joints[i-2];axis=definition.axis;normal=definition.normal;lo=definition.min;hi=definition.max;
   const ax=vec(axis),no=vec(normal);cfg.mPoint1=anchor;cfg.mPoint2=anchor;cfg.mHingeAxis1=ax;cfg.mHingeAxis2=ax;cfg.mNormalAxis1=no;cfg.mNormalAxis2=no;cfg.mLimitsMin=lo;cfg.mLimitsMax=hi;motor(cfg.mMotorSettings);J.destroy(ax);J.destroy(no);
  }else{
   const ax=vec(rotate(idle.q[i],[1,0,0])),no=vec(rotate(idle.q[i],[0,1,0]));cfg.mPosition1=anchor;cfg.mPosition2=anchor;cfg.mTwistAxis1=ax;cfg.mTwistAxis2=ax;cfg.mPlaneAxis1=no;cfg.mPlaneAxis2=no;
   const limits=targetRig.joints.joints[i-2].limits;cfg.mNormalHalfConeAngle=limits.normal;cfg.mPlaneHalfConeAngle=limits.plane;cfg.mTwistMinAngle=limits.twistMin;cfg.mTwistMaxAngle=limits.twistMax;motor(cfg.mSwingMotorSettings);motor(cfg.mTwistMotorSettings);J.destroy(ax);J.destroy(no);
  }
  const raw=cfg.Create(bodies[parent],bodies[i]),joint=J.castObject(raw,hinge?J.HingeConstraint:J.SwingTwistConstraint);system.AddConstraint(joint);
  if(hinge)joint.SetMotorState(J.EMotorState_Position);else {joint.SetSwingMotorState(J.EMotorState_Position);joint.SetTwistMotorState(J.EMotorState_Position);}
  joints.push({joint,i,parent,hinge,lo,hi,name:names[i],axis:hinge?rotate(qinv(idle.q[parent]),axis):null});J.destroy(cfg);J.destroy(anchor);
 }
 const tmpQ=quat([0,0,0,1]),tmpP=pos([0,0,0]);
 function setQ(q){tmpQ.Set(q[0],q[1],q[2],q[3]);return tmpQ;}
 function setP(p){tmpP.Set(p[0],p[1],p[2]);return tmpP;}
 let simulated=false,previousTarget=null,platforms=[],fallCap=20,kinematic=false,kinematicPose=null,kinematicVelocity=[0,0,0],gravity=9.81,targetSurfaces=[];
 const endpoints=new Array(names.length),linearCommands=new Array(names.length),offsets=bodies.map(b=>b?rotate(qinv(qa(b.GetRotation())),sub(arr(b.GetCenterOfMassPosition()),arr(b.GetPosition()))):null);
 const tempV=vec([0,0,0]),setV=a=>{tempV.Set(...a);return tempV;};
 const masses=[0,...rig.map(b=>b.mass)],totalMass=rig.mass;
 function com(velocity=false){if(kinematic&&velocity)return kinematicVelocity;let value=[0,0,0];for(let i=1;i<bodies.length;i++)value=add(value,mul(kinematic&&kinematicPose?add(kinematicPose.points[i],rotate(kinematicPose.q[i],offsets[i])):arr(velocity?bodies[i].GetLinearVelocity():bodies[i].GetCenterOfMassPosition()),masses[i]/totalMass));return value;}
 function configure({dynamic=false,edge=5,surfaces=null,cap=20,kinematic:kin=false,zeroGravity=false}={}){
  gravity=zeroGravity?0:9.81;targetSurfaces=surfaces||[];simulated=dynamic&&!kin;kinematic=kin;fallCap=cap;previousTarget=null;
  for(let i=1;i<bodies.length;i++)bi.SetMotionType(bodies[i].GetID(),kin||(!dynamic&&i===1)?J.EMotionType_Kinematic:J.EMotionType_Dynamic,J.EActivation_Activate);
  for(const j of joints){const state=dynamic||kin?J.EMotorState_Off:J.EMotorState_Position;if(j.hinge)j.joint.SetMotorState(state);else {j.joint.SetSwingMotorState(state);j.joint.SetTwistMotorState(state);}}
  system.SetGravity(setV(dynamic?[0,-gravity,0]:[0,0,0]));
  for(const platform of platforms){bi.RemoveBody(platform.GetID());bi.DestroyBody(platform.GetID());}platforms=[];
  if(dynamic)for(const box of surfaces?.map(s=>s.box)||[{center:[0,-.2,(edge-3)/2],dims:[3.6,.4,edge+3],forward:[1,0,0],side:[0,1,0],up:[0,0,1]}]){
   const half=vec(mul(box.dims,.5)),shape=new J.BoxShape(half,.02),p=pos(box.center),q=quat(R.fromAxes([box.forward,box.side,box.up])),cfg=new J.BodyCreationSettings(shape,p,q,J.EMotionType_Static,0);cfg.mFriction=.7;const body=bi.CreateBody(cfg);platforms.push(body);bi.AddBody(body.GetID(),J.EActivation_DontActivate);for(const v of [half,p,q,cfg])J.destroy(v);
  }
 }
 function advance(p,dt){
  p=targetRig.project(p,targetSurfaces);
  if(kinematic){const old=com();kinematicPose=p;kinematicVelocity=mul(sub(com(),old),1/dt);return;}
  if(!simulated)bi.MoveKinematic(bodies[1].GetID(),setP(p.points[1]),setQ(p.q[1]),dt);
  else {
   // Native FVelocityServo::CalculateRewrite / PredictCommandFrame, strength 1:
   // error / substep, parent-first commanded endpoint, no added previous-frame feed-forward.
   // Only the pelvis has an absolute position servo. Carry compatible anchor
   // velocities down the chain, so the joint solver does not fight the angular
   // commands to restore attachment. No limb receives a world-position target.
   for(let i=1;i<bodies.length;i++){
    const body=bodies[i],actual=qa(body.GetRotation()),target=i===1?p.q[i]:qm(endpoints[parents[i]],qm(qinv(p.q[parents[i]]),p.q[i]));
    let angular=mul(R.qlog(qm(target,qinv(actual))),1/dt);const speed=length(angular);if(speed>1000)angular=mul(angular,1000/speed);
    bi.SetAngularVelocity(body.GetID(),setV(angular));endpoints[i]=qm(R.qexp(mul(angular,dt)),actual);
    if(i===1){const linear=add(mul(sub(add(p.points[i],rotate(endpoints[i],offsets[i])),arr(body.GetCenterOfMassPosition())),1/dt),[0,gravity*dt,0]);linearCommands[i]=linear;bi.SetLinearVelocity(body.GetID(),setV(linear));}else{const parent=parents[i],j=joints[i-2],ap=j.hinge?j.joint.GetLocalSpacePoint1():j.joint.GetLocalSpacePosition1(),ac=j.hinge?j.joint.GetLocalSpacePoint2():j.joint.GetLocalSpacePosition2(),parentQ=qa(bodies[parent].GetRotation()),deltaParent=sub(rotate(endpoints[parent],arr(ap)),rotate(parentQ,arr(ap))),deltaChild=sub(rotate(endpoints[i],arr(ac)),rotate(actual,arr(ac)));linearCommands[i]=add(linearCommands[parent],mul(sub(deltaParent,deltaChild),1/dt));bi.SetLinearVelocity(body.GetID(),setV(linearCommands[i]));}
   }
  }
  if(!simulated)for(const j of joints)j.joint.SetTargetOrientationBS(setQ(qm(qinv(p.q[j.parent]),p.q[j.i])));
  world.Step(dt,1);previousTarget=p;
  if(simulated){const excess=-fallCap-com(true)[1];if(excess>0)for(let i=1;i<bodies.length;i++)bi.SetLinearVelocity(bodies[i].GetID(),setV(add(arr(bodies[i].GetLinearVelocity()),[0,excess,0])));}
 }
 // Resolve fast turns with smaller steps; ordinary 240 Hz playback pays no
 // extra simulation cost. The old 60 rad/s cap silently discarded fast/tucked
 // commands. Intermediate targets interpolate local joints, not world points.
 function drive(p,dt){
  p=targetRig.project(p,targetSurfaces);
  const from=previousTarget;
  const angle=simulated&&from?Math.max(...p.q.slice(1).map((q,i)=>length(R.qlog(qm(q,qinv(from.q[i+1])))))):0;
  const count=Math.max(1,Math.min(32,Math.ceil(angle/.06)));
  // Root is a nonphysical animation reference and can change basis at release.
  // Use one basis for both endpoints so interpolation preserves the pelvis's
  // world path; local limb interpolation and real platform contacts remain.
  const aligned=count>1?{...from,q:[p.q[0],...from.q.slice(1)]}:from;
  for(let i=1;i<=count;i++)advance(i===count?p:C.blend(aligned,p,i/count,manifest.parents),dt/count);
 }
 function reset(p,velocity=[0,0,0]){p=targetRig.project(p,targetSurfaces);kinematicPose=p;kinematicVelocity=velocity;previousTarget=p;for(let i=1;i<bodies.length;i++){bi.SetPositionAndRotation(bodies[i].GetID(),setP(p.points[i]),setQ(p.q[i]),J.EActivation_Activate);bi.SetLinearAndAngularVelocity(bodies[i].GetID(),setV(velocity),zero);}}
 function read(){if(kinematic)return kinematicPose;const points=[previousTarget?.points[0]||[0,0,0]],q=[previousTarget?.q[0]||[0,0,0,1]];for(let i=1;i<bodies.length;i++){points.push(arr(bodies[i].GetPosition()));q.push(qa(bodies[i].GetRotation()));}return {points,q,axes:q.map(R.toAxes)};}
 function diagnostics(){const p=read();let anchorError=0;for(const c of joints){const a=c.hinge?c.joint.GetLocalSpacePoint1():c.joint.GetLocalSpacePosition1(),b=c.hinge?c.joint.GetLocalSpacePoint2():c.joint.GetLocalSpacePosition2();const pa=add(arr(bodies[c.parent].GetCenterOfMassPosition()),rotate(p.q[c.parent],arr(a))),pb=add(arr(bodies[c.i].GetCenterOfMassPosition()),rotate(p.q[c.i],arr(b)));anchorError=Math.max(anchorError,length(sub(pa,pb)));}return {bodies:bodies.length-1,dynamicBodies:bodies.slice(1).filter(b=>b.IsDynamic()).length,pelvisDynamic:bodies[1].IsDynamic(),joints:joints.length,hinges:joints.filter(j=>j.hinge).map(j=>({name:j.name,angle:j.joint.GetCurrentAngle(),min:j.lo,max:j.hi})),anchorError,finite:p.points.flat().concat(p.q.flat()).every(Number.isFinite)};}
 function targetDiagnostics(p){return joints.map(c=>{const rest=qm(qinv(idle.q[c.parent]),idle.q[c.i]),local=qm(qinv(p.q[c.parent]),p.q[c.i]),delta=qm(local,qinv(rest)),v=R.qlog(delta),angle=c.hinge?dot(v,c.axis):null,off=c.hinge?length(sub(v,mul(c.axis,angle))):0,anchor=add(p.points[c.parent],rotate(p.q[c.parent],rotate(qinv(idle.q[c.parent]),sub(idle.points[c.i],idle.points[c.parent]))));return {name:c.name,hinge:c.hinge,angle,off,rotation:length(v),anchor:length(sub(anchor,p.points[c.i]))};});}
 function torsoGeometry(){return torso.map(spec=>{const shape=J.castObject(bodies[spec.bone].GetShape(),J.RotatedTranslatedShape),box=J.castObject(shape.GetInnerShape(),J.BoxShape);return {name:spec.name,box:box.GetSubType()===J.EShapeSubType_Box,dims:mul(arr(box.GetHalfExtent()),2),offset:arr(shape.GetPosition()),rotation:qa(shape.GetRotation())};});}
 function massProperties(){return rig.map(s=>{const mp=bodies[s.i].GetShape().GetMassProperties();mp.ScaleToMass(s.mass);const m=mp.mInertia;return {name:s.name,mass:s.mass,offset:offsets[s.i],inertia:[arr(m.GetAxisX()),arr(m.GetAxisY()),arr(m.GetAxisZ())]};});}
 return {step:drive,reset,target:p=>targetRig.project(p,targetSurfaces),targetRig,read,diagnostics,targetDiagnostics,configure,com,rig,massProperties,torso,torsoGeometry,torsoWorld:()=>torso.map(s=>T.world(read(),s)),get simulated(){return simulated;},dispose(){for(const platform of platforms){bi.RemoveBody(platform.GetID());bi.DestroyBody(platform.GetID());}for(const j of joints)system.RemoveConstraint(j.joint);for(const b of bodies.slice(1)){bi.RemoveBody(b.GetID());bi.DestroyBody(b.GetID());}J.destroy(tempV);J.destroy(tmpQ);J.destroy(tmpP);J.destroy(zero);J.destroy(world);},engine:'Jolt WASM 1.1.1'};
}
