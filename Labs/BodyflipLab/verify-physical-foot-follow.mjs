import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),SC=require('./spin-contact.js'),P=require('./physical-flight.js'),M=require('./mass.js'),T=require('./target-rig.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest),rig=M.model(names,parents,reference),targets=T.create(names,parents,reference),dt=1/240;
const shifted=(p,d)=>({...p,points:p.points.map(v=>R.add(v,d))}),distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI,qa=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let checks=0,maxAim=0,maxMomentum=0,maxCOM=0,maxStep=0;const check=(value,message)=>{assert(value,message);checks++;};
for(const follow of [0,.08])for(const side of ['L','R'])for(const inclination of [0,Math.PI/4])for(const spin of [0,4,-4]){
 const tilt=R.qexp([0,0,inclination]),base=shifted(reference,[0,1,0]),l=S.leg(base,names,side),ankle=R.add(base.points[l.hip],R.mul(R.sub(base.points[l.foot],base.points[l.hip]),.82));
 let departure=targets.project(S.solve(base,l,ankle,parents,.99));departure={...departure,points:departure.points.map(v=>R.rotate(tilt,v)),q:departure.q.map(q=>R.qm(tilt,q))};departure.axes=departure.q.map(R.toAxes);
 const limb=S.leg(departure,names,side),surface=S.platformSurface({id:'floor',position:[0,-2,0],size:[20,.2,20],rotation:tilt}),settings=C.sanitize({legFollow:follow,legBlend:.2,momentum3D:side==='L',footRollSpeed:180}),center=M.center(departure,rig),axis=R.rotate(tilt,[1,0,0]),velocity=R.rotate(tilt,[0,2,1]);
 const zero={from:[0,0,0],to:[0,0,0],begin:0,duration:0},plan={referenceI:M.tensor(departure,rig),flip:{...zero,to:R.mul(axis,spin)},twist:zero};
 const source=t=>{const age=Math.max(0,t),q=R.qexp(R.mul(axis,spin*age)),pose=shifted(M.rotateAboutCOM(departure,q,rig),R.mul(velocity,t));return {pose,root:pose.points[0],phase:'RISE',supportState:t<0?'PIN':'FREE',spin:{q,rotation:q,spinPlan:plan}};};
 const segment={support:{leg:limb},supportKind:'foot',airStart:0,jumpStart:0,contactTime:-.1,supportStart:-.2,surface,surfaces:[surface],bounce:{didPush:true},spin:{active:spin!==0,sample:source},unturned:source};
 const contacts=SC.create(segment,settings,names,parents,reference),history=(t,project)=>{const f=source(Math.min(t,-1e-7));return project?{...f,pose:project(f.pose)}:f;};
 const flight=P.create(source,{start:0,settings,names,parents,reference,gravity:0,balance:spin!==0,articulation:context=>contacts.physicalFollow(context,history,p=>p)}),point=history(-1e-7,p=>targets.project(p,[surface])).pose.points[limb.foot];
 let previous=null,firstToeAngle=null;
 for(let i=1;i<=72;i++){
  const t=i*dt,f=flight.sample(t),p=targets.project(f.pose),local=R.localize(p.points,p.q,parents);
  if(t<settings.legFollow){maxAim=Math.max(maxAim,angle(R.sub(p.points[limb.foot],p.points[limb.hip]),R.sub(point,p.points[limb.hip])));}
  const toeAngle=angle(S.footFrame(p,limb.foot,limb.toe,side).forward,R.sub(p.points[limb.foot],p.points[limb.knee]));firstToeAngle??=toeAngle;
  if(follow>0&&spin===0&&i===18)check(toeAngle<firstToeAngle-5,'Toes extend toward the shin direction after release');
  maxMomentum=Math.max(maxMomentum,f.physical.error);maxCOM=Math.max(maxCOM,distance(M.center(p,rig),R.add(center,R.mul(velocity,t))));
  if(previous)for(const k of [limb.hip,limb.knee,limb.foot])maxStep=Math.max(maxStep,qa(local.q[k],previous.q[k])*180/Math.PI);
  check(p.points.flat().every(Number.isFinite),'Finite final pose');check(contacts.activeBones(t).length===0,'Follow does not renew contact');
  check(Math.abs(distance(p.points[limb.hip],p.points[limb.knee])-limb.upper)<1e-7&&Math.abs(distance(p.points[limb.knee],p.points[limb.foot])-limb.lower)<1e-7,'Leg lengths retained');
  if(t>settings.legFollow+settings.legBlend){const raw=R.localize(source(t).pose.points,source(t).pose.q,parents);check([limb.hip,limb.knee,limb.foot].every(k=>qa(local.q[k],raw.q[k])<1e-8),'Return finishes on time');}
  previous=local;
 }
 const snapshot=JSON.stringify(flight.sample(.047));flight.sample(.4);flight.sample(.01);check(JSON.stringify(flight.sample(.047))===snapshot,'Reverse seek is deterministic');
}
check(maxAim<3,'Released leg points toward its fixed world contact through the body turn');check(maxMomentum<.001,'Final constrained articulation participates in momentum balance');check(maxCOM<1e-7,'Follow preserves the ballistic COM');check(maxStep<10,'No quarter-frame joint pop');
console.log(JSON.stringify({passed:true,checks,maxAim,maxMomentum,maxCOM,maxStep},null,2));
