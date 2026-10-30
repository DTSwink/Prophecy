// Lightweight wrist-frame/limit tests, including the shipped Jolt WASM clamp.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import initJolt from './vendor/jolt.mjs';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),W=require('./wrist.js'),manifest=JSON.parse(fs.readFileSync(new URL('./data/manifest.json',import.meta.url))),ref=C.poseFromShared(manifest),{names,parents}=manifest;
const {qm,qinv,qexp,qlog,rotate,mul,sub,length,dot}=R,angle=(a,b)=>length(qlog(qm(a,qinv(b)))),near=(a,b,t=1e-8)=>assert(length(sub(a,b))<t),deg=Math.PI/180,checks=[];
function check(name,test){assert(test,name);checks.push(name);}
for(const side of ['L','R']){
 const hand=names.indexOf('hand_'+side.toLowerCase()),parent=parents[hand],w=W.create(ref,parent,hand,side),qp=ref.q[parent],qh=ref.q[hand];
 near(w.toConstraint(qp,qh),[0,0,0,1]);
 for(const [r,expected] of [[[0,0,-39],true],[[0,0,-41],false],[[54,0,0],true],[[56,0,0],false],[[0,44,0],true],[[0,46,0],false]]){
  const q=qm(qh,qexp(mul(r,deg)));
  check(side+' anatomical axis '+r,w.inspect(qp,q).within===expected);
 }
 for(let i=0;i<121;i++){
  const q=qexp([Math.sin(i*.71)*2.8,Math.cos(i*.19)*2.2,Math.sin(i*.37)*2.1]),bounded=W.clampConstraint(q);
  check(side+' clamp inside '+i,W.inspectConstraint(bounded).within);
  check(side+' clamp idempotent '+i,angle(bounded,W.clampConstraint(bounded))<1e-8);
  const world=w.fromConstraint(qp,bounded);check(side+' frame inverse '+i,angle(bounded,w.toConstraint(qp,world))<1e-8);
  const normal=R.unit([Math.sin(i*.3),Math.cos(i*.41),Math.sin(i*.23)]),out=w.aim(qp,world,normal),before=W.decompose(bounded),after=W.decompose(w.toConstraint(qp,out));
  check(side+' aimed limit '+i,w.inspect(qp,out).within);
  check(side+' no added twist '+i,Math.abs(before.angle-after.angle)<1e-8);
  check(side+' no added sideways bend '+i,Math.abs(before.swing[2]-after.swing[2])<1e-8);
  check(side+' backward extension only '+i,after.swing[1]>=before.swing[1]-1e-8);
  const palm=q=>rotate(q,[0,side==='L'?1:-1,0]);check(side+' palm does not worsen '+i,dot(palm(out),mul(normal,-1))>=dot(palm(world),mul(normal,-1))-1e-10);
  for(const weight of [0,.2,.5,.9,1])check(side+' blend inside '+i+'/'+weight,w.inspect(qp,w.aim(qp,world,normal,weight)).within);
 }
}
// Symmetric rigs and reflected target must produce reflected palm directions.
const identity=[0,0,0,1],mirror=q=>[q[0],-q[1],-q[2],q[3]],reflection=v=>[-v[0],v[1],v[2]],flip=qexp([Math.PI,0,0]),left=W.create({q:[identity,identity]},0,1,'L'),right=W.create({q:[identity,flip]},0,1,'R');
let maxMirror=0,maxDelta=0;
for(let i=0;i<=200;i++){
 const parent=qexp([.23,Math.sin(i/100)*.7,-.2]),other=mirror(parent),normal=R.unit([Math.sin(i*.07),Math.cos(i*.03),.4]),a=left.aim(parent,parent,normal),b=right.aim(other,qm(other,flip),reflection(normal));
 maxMirror=Math.max(maxMirror,length(sub(reflection(rotate(a,[0,1,0])),rotate(b,[0,-1,0]))));
 const next=left.aim(parent,parent,R.unit([normal[0]+1e-6,normal[1],normal[2]]));maxDelta=Math.max(maxDelta,angle(a,next));
}
check('mirrored palm aim',maxMirror<1e-8);check('small target deltas remain continuous',maxDelta<1e-3);
const opposed=left.aim(identity,identity,[0,1,0]);check('inverted palm attempts full legal extension',Math.abs(left.inspect(identity,opposed).swing[1]-Math.sin(W.limits.plane/2))<1e-7);
check('inverted palm stays inclined',dot(rotate(opposed,[0,1,0]),[0,1,0])>0);

// Compare both frame transforms and clamped targets to the actual local runtime.
const J=await initJolt(),settings=new J.JoltSettings();settings.mMaxWorkerThreads=0;
const filter=new J.ObjectLayerPairFilterTable(1);filter.EnableCollision(0,0);const bp=new J.BroadPhaseLayerInterfaceTable(1,1),layer=new J.BroadPhaseLayer(0);bp.MapObjectToBroadPhaseLayer(0,layer);J.destroy(layer);settings.mObjectLayerPairFilter=filter;settings.mBroadPhaseLayerInterface=bp;settings.mObjectVsBroadPhaseLayerFilter=new J.ObjectVsBroadPhaseLayerFilterTable(bp,1,filter,1);
const world=new J.JoltInterface(settings);J.destroy(settings);const bi=world.GetPhysicsSystem().GetBodyInterface(),qa=q=>[q.GetX(),q.GetY(),q.GetZ(),q.GetW()];let maxJolt=0;
for(const side of ['L','R']){
 const h=names.indexOf('hand_'+side.toLowerCase()),p=parents[h],w=W.create(ref,p,h,side),created=[],shape=new J.SphereShape(.02),point=new J.RVec3(0,0,0);
 for(const i of [p,h]){const q=new J.Quat(...ref.q[i]),cfg=new J.BodyCreationSettings(shape,point,q,J.EMotionType_Dynamic,0);created.push(bi.CreateBody(cfg));J.destroy(cfg);J.destroy(q);}
 const cfg=new J.SwingTwistConstraintSettings(),x=new J.Vec3(...rotate(ref.q[h],[1,0,0])),y=new J.Vec3(...rotate(ref.q[h],[0,1,0]));cfg.mPosition1=point;cfg.mPosition2=point;cfg.mTwistAxis1=x;cfg.mTwistAxis2=x;cfg.mPlaneAxis1=y;cfg.mPlaneAxis2=y;cfg.mNormalHalfConeAngle=W.limits.normal;cfg.mPlaneHalfConeAngle=W.limits.plane;cfg.mTwistMinAngle=W.limits.twistMin;cfg.mTwistMaxAngle=W.limits.twistMax;
 const joint=J.castObject(cfg.Create(...created),J.SwingTwistConstraint),c1=joint.GetConstraintToBody1(),c2=joint.GetConstraintToBody2();check(side+' Jolt parent frame',angle(qa(c1),w.constraintToParent)<1e-6);check(side+' Jolt child frame',angle(qa(c2),W.basis)<1e-6);
 for(let i=0;i<121;i++){const q=qexp([Math.sin(i*.71)*2.8,Math.cos(i*.19)*2.2,Math.sin(i*.37)*2.1]),j=new J.Quat(...q);joint.SetTargetOrientationCS(j);const target=joint.GetTargetOrientationCS(),error=angle(qa(target),W.clampConstraint(q));maxJolt=Math.max(maxJolt,error);check(side+' Jolt clamp parity '+i,error<3e-5);J.destroy(j);}
 J.destroy(joint);for(const body of created)bi.DestroyBody(body.GetID());for(const v of [cfg,x,y,point])J.destroy(v);
}
J.destroy(world);console.log(JSON.stringify({checks:checks.length,maxJoltError:maxJolt,maxMirrorError:maxMirror,maxTargetDelta:maxDelta},null,2));
