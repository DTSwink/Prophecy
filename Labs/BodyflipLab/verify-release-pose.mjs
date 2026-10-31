import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),SC=require('./spin-contact.js'),T=require('./target-rig.js'),M=require('./mass.js'),P=require('./physical-flight.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest),targets=T.create(names,parents,reference),mass=M.model(names,parents,reference);
const shifted=(p,d)=>({...p,points:p.points.map(v=>R.add(v,d))}),distance=(a,b)=>R.length(R.sub(a,b)),qa=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let checks=0,maxRebaseError=0;
const check=(condition,label)=>{assert(condition,label);checks++;};

// The collision carrier may translate an entire trajectory. A foot's local
// follow/recovery must not change because its source uses another origin.
for(const side of ['L','R'])for(const incline of [0,Math.PI/4]){
 const turn=R.qexp([0,0,incline]),pose={points:reference.points.map(v=>R.rotate(turn,R.add(v,[0,.2,0]))),q:reference.q.map(q=>R.qm(turn,q))};pose.axes=pose.q.map(R.toAxes);
 const surfaces=[S.platformSurface({id:'floor',position:R.rotate(turn,[0,-.2,0]),size:[20,.4,20],rotation:turn})],leg=S.leg(pose,names,side),release=1;
 const make=offset=>{
  const world=t=>shifted(pose,[0,.3*(t-release),.5*(t-release)]),source=t=>{const p=shifted(world(t),offset);return {pose:p,root:p.points[0],supportState:t<release?'PIN':'FREE'};};
  const segment={support:{leg},supportKind:'foot',airStart:release,jumpStart:.9,contactTime:.9,supportStart:.8,surfaces,surface:surfaces[0],bounce:{didPush:true},spin:{active:true,sample:source},unturned:source};
  const settings=C.sanitize({legFollow:.2,legBlend:.2}),contact=SC.create(segment,settings,names,parents,reference);
  const history=(t,project)=>{const p=project?project(world(t)):world(t),f=source(t);return {...f,pose:shifted(p,offset)};};
  return t=>contact.apply(source(t).pose,t,source(t),null,history);
 };
 const unshifted=make([0,0,0]);
 for(const offset of [[0,-.35,0],[1.2,-.8,-2],[0,.4,3]]){
  const rebased=make(offset);
  for(const time of [1.0001,1.04,1.15,1.23,1.35,1.41]){
   const a=unshifted(time),b=rebased(time),al=R.localize(a.points,a.q,parents),bl=R.localize(b.points,b.q,parents);
   for(const i of [leg.hip,leg.knee,leg.foot,leg.toe]){const error=qa(al.q[i],bl.q[i]);maxRebaseError=Math.max(maxRebaseError,error);check(error<1e-9,'Release projection is independent of the source origin');}
   check(distance(M.center(b,mass),R.add(M.center(a,mass),offset))<1e-9,'Rebasing preserves the same COM trajectory');
  }
 }
}

// Momentum is inherited from contact, while the free-flight pose starts with
// the captured constrained articulation. No correction should be interpreted
// as a zero-time limb movement that kicks the whole body in the opposite way.
const local=R.localize(reference.points,reference.q,parents),q=local.q.slice(),hip=names.indexOf('thigh_l');q[hip]=R.qm(R.qexp([.3,0,0]),q[hip]);
const departure=targets.project(R.fk({p:local.p,q},parents)),center=M.center(reference,mass),actual=shifted(departure,R.sub(center,M.center(departure,mass)));
const seed=t=>({pose:shifted(reference,[t,2*t,0]),root:R.add(reference.points[0],[t,2*t,0]),phase:'RISE'}),source=t=>({pose:actual,root:actual.points[0],phase:'RISE'});
const flight=P.create(source,{start:0,seedSource:seed,settings:{momentum3D:true},names,parents,reference,gravity:0});
const frame=flight.sample(1e-6);
check(qa(frame.physical.rotation,[0,0,0,1])<1e-9,'No artificial rigid reaction at the constrained-pose handoff');
check(distance(frame.physical.velocity,[1,2,0])<1e-8,'Contact COM velocity is retained');
check(distance(frame.physical.com,R.add(center,[1e-6,2e-6,0]))<1e-8,'Contact COM position is retained');
check(frame.pose.q.every((v,i)=>qa(v,actual.q[i])<1e-9),'Captured departure articulation is retained');
console.log(JSON.stringify({passed:true,checks,maxRebaseError},null,2));
