import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),lab='../../Labs/BodyflipLab/',R=require(lab+'recovery.js'),C=require(lab+'core.js'),S=require(lab+'support.js'),H=require(lab+'hand-support.js'),P=require(lab+'rig-profile.js'),J=require(lab+'joint-rig.js');
const m=JSON.parse(fs.readFileSync('Labs/BodyflipLab/data/manifest.json','utf8')),reference=C.poseFromShared(m),profile=JSON.parse(fs.readFileSync('Labs/BodyflipLab/fixtures/native-rig.json','utf8'));P.install(profile,m.names,m.parents);H.registerRig(reference);
const rig=J.create(m.names,m.parents,reference),source=rig.project(reference);let checks=0,maxEndpoint=0,maxJoint=0,maxAnchor=0;const steps=[];
for(const count of [120,480]){let maxStep=0;
for(const hand of [false,true])for(const side of ['L','R'])for(const turn of [[0,0,0],[Math.PI,0,0],[.5,1.2,-.7]]){
 const q=R.qexp(turn),p={points:source.points.map(v=>R.rotate(q,v)),q:source.q.map(v=>R.qm(q,v))};p.axes=p.q.map(R.toAxes);
 const l=hand?H.arm(p,m.names,side):S.leg(p,m.names,side),hinge=rig.joints.find(j=>j.i===l.knee),end=rig.joints.find(j=>j.i===l.foot),u=hinge.parentFrame.p,v=R.sub(end.parentFrame.p,hinge.childFrame.p);let previous=null;
 for(let tick=0;tick<=count;tick++){
  const t=tick/count,angle=hinge.min+(hinge.max-hinge.min)*(.05+.9*t),localQ=rig.fromCoordinates([angle],hinge),reach=R.add(u,R.rotate(localQ,v));
  const upper=R.qm(R.qexp([.12*Math.sin(t*4),.2*Math.cos(t*120/35),0]),p.q[l.hip]),target=R.add(p.points[l.hip],R.rotate(upper,reach));
  const solved=S.solve(p,l,target,m.parents,1,l),local=R.localize(solved.points,solved.q,m.parents),error=R.length(R.sub(solved.points[l.foot],target));
  maxEndpoint=Math.max(maxEndpoint,error);maxJoint=Math.max(maxJoint,R.length(R.qlog(R.qm(local.q[l.knee],R.qinv(rig.clampLocal(local.q[l.knee],hinge))))));
  for(const j of [hinge,end])maxAnchor=Math.max(maxAnchor,R.length(R.sub(R.add(solved.points[j.parent],R.rotate(solved.q[j.parent],j.parentFrame.p)),R.add(solved.points[j.i],R.rotate(solved.q[j.i],j.childFrame.p)))));
  if(previous)maxStep=Math.max(maxStep,R.length(R.qlog(R.qm(solved.q[l.hip],R.qinv(previous.q[l.hip])))));previous=solved;checks++;
 }
}steps.push(maxStep);}
assert(maxEndpoint<1e-6,'Native connector target must remain exact');assert(maxJoint<1e-8,'Native hinge must already satisfy its real limit');assert(maxAnchor<1e-8,'Both connectors must coincide');assert(steps[1]<steps[0]*.35&&steps[1]<.05,'Bend-plane changes must converge with sample spacing, rather than jump branches');
console.log(JSON.stringify({checks,maxEndpoint,maxJoint,maxAnchor,steps}));
