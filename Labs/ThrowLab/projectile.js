import initJolt from './vendor/jolt.js';

// Only one released object. Fixed 120 Hz simulation, cached for deterministic
// seeking/loops; no stepping while held, paused, or after the body has slept.
export async function createProjectileSystem(assets,R=globalThis.Recovery,V=globalThis.ThrowVanilla){
 const J=await initJolt(),{add,sub,mul,rotate,qm,qinv,qlog,qslerp}=R;
 const vec=a=>new J.Vec3(...a),pos=a=>new J.RVec3(...a),quat=a=>new J.Quat(...a),arr=v=>[v.GetX(),v.GetY(),v.GetZ()],qa=q=>[q.GetX(),q.GetY(),q.GetZ(),q.GetW()];
 const config=new J.JoltSettings();config.mMaxWorkerThreads=0;
 const filter=new J.ObjectLayerPairFilterTable(2);filter.EnableCollision(0,1);
 const bp=new J.BroadPhaseLayerInterfaceTable(2,2);
 for(let i=0;i<2;i++){const layer=new J.BroadPhaseLayer(i);bp.MapObjectToBroadPhaseLayer(i,layer);J.destroy(layer);}
 config.mObjectLayerPairFilter=filter;config.mBroadPhaseLayerInterface=bp;
 config.mObjectVsBroadPhaseLayerFilter=new J.ObjectVsBroadPhaseLayerFilterTable(bp,2,filter,2);
 const world=new J.JoltInterface(config);J.destroy(config);
 const system=world.GetPhysicsSystem(),bi=system.GetBodyInterface(),gravity=vec([0,-9.81,0]);system.SetGravity(gravity);J.destroy(gravity);
 const physicsSettings=system.GetPhysicsSettings();physicsSettings.mPenetrationSlop=.0005;physicsSettings.mNumPositionSteps=8;system.SetPhysicsSettings(physicsSettings);
 const shapes={},longAxes={},owned=[];
 for(const [key,asset] of Object.entries(assets)){
  const hulls=[];
  for(const points of asset.hulls||[asset.collision]){
   const settings=new J.ConvexHullShapeSettings();settings.mMaxConvexRadius=.001;
   for(const point of points){const v=vec(point);settings.mPoints.push_back(v);J.destroy(v);}
   const result=settings.Create();if(result.HasError())throw Error('Invalid '+key+' collision hull');
   hulls.push(result.Get());owned.push(result,settings);
  }
  if(hulls.length===1)shapes[key]=hulls[0];else{
   const settings=new J.StaticCompoundShapeSettings(),p=vec([0,0,0]),q=quat([0,0,0,1]);
   for(const hull of hulls)settings.AddShapeShape(p,q,hull,0);
   J.destroy(p);J.destroy(q);const result=settings.Create();if(result.HasError())throw Error('Invalid '+key+' compound');
   shapes[key]=result.Get();owned.push(result,settings);
  }
  // The least-inertia principal axis follows the sword's length, in hand space.
  const mass=shapes[key].GetMassProperties(),m=mass.mInertia,cols=[arr(m.GetAxisX()),arr(m.GetAxisY()),arr(m.GetAxisZ())],trace=cols[0][0]+cols[1][1]+cols[2][2];
  let axis=R.unit([1,.4,.8]);for(let n=0;n<64;n++)axis=R.unit(axis.map((v,i)=>trace*v-cols.reduce((sum,col,j)=>sum+col[i]*axis[j],0)));
  const tip=asset.collision.reduce((a,b)=>R.dot(a,a)>R.dot(b,b)?a:b);if(R.dot(axis,tip)<0)axis=mul(axis,-1);longAxes[key]=asset.longAxis?R.unit(asset.longAxis):axis;J.destroy(mass);
 }
 const bodies=[];let body=null,signature=null,frames=[],release=0,steps=0,seed=null,previewKey=null,previewSeed=null;
 const dt=1/120;
 function removeAll(){for(const b of bodies){bi.RemoveBody(b.GetID());bi.DestroyBody(b.GetID());}bodies.length=0;body=null;}
 function make(shape,p,q,dynamic,mass=1){
  const vp=pos(p),vq=quat(q),s=new J.BodyCreationSettings(shape,vp,vq,dynamic?J.EMotionType_Dynamic:J.EMotionType_Static,dynamic?1:0);
  s.mFriction=.55;s.mRestitution=.25;s.mLinearDamping=0;s.mAngularDamping=.03;s.mAllowSleeping=true;
  // Long, thin objects need gyroscopic coupling to tumble after an off-axis hit.
  if(dynamic){s.mApplyGyroscopicForce=true;s.mMotionQuality=J.EMotionQuality_LinearCast;s.mMaxLinearVelocity=1000;s.mMaxAngularVelocity=1000;s.mOverrideMassProperties=J.EOverrideMassProperties_CalculateInertia;s.mMassPropertiesOverride.mMass=mass;}
  const b=bi.CreateBody(s);bi.AddBody(b.GetID(),dynamic?J.EActivation_Activate:J.EActivation_DontActivate);bodies.push(b);
  for(const value of [s,vp,vq])J.destroy(value);return b;
 }
 function held(pose,hand,o){
  const bind=assets[o.kind].bind||{},grip=o.grip||{},base=qm(pose.q[hand],bind.rotation||[0,0,0,1]);
  const origin=add(pose.points[hand],rotate(pose.q[hand],bind.position||[0,0,0]));
  return {p:add(origin,rotate(base,grip.position||[0,0,0])),q:qm(base,grip.rotation?V.rotation(grip.rotation):[0,0,0,1]),phase:'held'};
 }
 function read(){return {p:arr(body.GetPosition()),q:R.unit(qa(body.GetRotation())),v:arr(body.GetLinearVelocity()),omega:arr(body.GetAngularVelocity()),active:body.IsActive()};}
 const scaleOf=o=>[0,1,2].map(i=>{const v=Array.isArray(o.scale)?o.scale[i]:o.scale;return Number.isFinite(v)?Math.max(.1,Math.min(2,v)):1;});
 const keyOf=o=>JSON.stringify([o.key,o.kind,o.release,o.target,o.radius,o.controls,o.grip,scaleOf(o)]);
 function preview(o){
  const key=keyOf(o);if(key===previewKey)return previewSeed;
  const pose=o.sample(o.release),a=held(pose,o.hand,o),com=arr(shapes[o.kind].GetCenterOfMass()).map((v,i)=>v*scaleOf(o)[i]);
  const h=1/120,t0=Math.max(0,o.release-h),t1=o.release>0?o.release:Math.min(o.duration,h),p0=held(o.sample(t0),o.hand,o),p1=held(o.sample(t1),o.hand,o),delta=t1-t0;
  const authoredVelocity=delta>0?mul(sub(add(p1.p,rotate(p1.q,com)),add(p0.p,rotate(p0.q,com))),1/delta):[0,0,0];
  const authoredOmega=delta>0?mul(qlog(qm(p1.q,qinv(p0.q))),1/delta):[0,0,0];
  const adjusted=o.controls?V.launch(authoredVelocity,authoredOmega,a.q,pose.q[0],longAxes[o.kind],o.controls):{velocity:authoredVelocity,omega:authoredOmega};
  previewKey=key;return previewSeed={p:a.p,q:a.q,v:adjusted.velocity,omega:adjusted.omega,comOffset:com,axis:adjusted.axis,twist:adjusted.twist,authoredTwist:adjusted.authoredTwist,authoredVelocity};
 }
 function start(o,key){
  removeAll();signature=key;frames=[];steps=0;release=o.release;
  const half=vec([100,.25,100]),floorShape=new J.BoxShape(half,.01);J.destroy(half);
  make(floorShape,[0,-.25,0],[0,0,0,1],false);
  // Body owns the reference-counted shapes; do not destroy their borrowed pointers.
  const targetShape=new J.SphereShape(o.radius);make(targetShape,o.target,[0,0,0,1],false);
  seed=structuredClone(preview(o));const {v:velocity,omega}=seed;
  let shape=shapes[o.kind];const scale=scaleOf(o);
  if(scale.some(v=>v!==1)){const v=vec(scale);shape=new J.ScaledShape(shape,v);J.destroy(v);}
  body=make(shape,seed.p,seed.q,true,assets[o.kind].mass);
  const v=vec(velocity),w=vec(omega);bi.SetLinearAndAngularVelocity(body.GetID(),v,w);J.destroy(v);J.destroy(w);
  Object.assign(seed,{gyroscopic:body.GetApplyGyroscopicForce(),allowedDOFs:body.GetMotionProperties().GetAllowedDOFs()});frames.push(read());
 }
 function at(t,o){
  const key=keyOf(o);
  if(key!==signature){removeAll();signature=null;frames=[];seed=null;steps=0;}
  if(t<o.release)return held(o.pose||o.sample(t),o.hand,o);
  if(!body)start(o,key);
  const f=Math.max(0,(t-release)/dt),i=Math.floor(f+1e-9),fraction=Math.max(0,Math.min(1,f-i)),u=fraction<1e-9?0:fraction,needed=i+(u>0?1:0);
  while(frames.length<=needed){if(body.IsActive()){world.Step(dt,1);steps++;frames.push(read());}else frames.push(frames.at(-1));}
  const a=frames[i],b=frames[Math.min(i+1,frames.length-1)];
  return {p:add(a.p,mul(sub(b.p,a.p),u)),q:u===0?a.q.slice():qslerp(a.q,b.q,u),v:a.v,omega:a.omega,phase:a.active?'released':'resting'};
 }
 return {at,preview,held:o=>held(o.pose||o.sample(o.release),o.hand,o),get diagnostics(){return {engine:'Jolt WASM 1.1.1',steps,cachedFrames:frames.length,bodies:bodies.length,seed};},dispose(){removeAll();for(const value of owned.reverse())J.destroy(value);J.destroy(world);}};
}
