'use strict';
// Small publication boundary for a prospective stair plan. Actual NN history
// remains untouched. Only the planned terrain correction is transferred.
const R=require('../../Labs/FootIKLab/recovery.js'),K=require('../../Labs/FootIKLab/footik.js');
const LiveTerrain=require('./live-terrain.cjs');
const {add,sub,mul,length,rotate,qm,qinv}=R;
function join(a){
 const frame=a.candidate,actual=a.current,parents=a.parents,names=a.names||['root',...a.sourceNames];
 if(!frame?.pose||!frame.raw||!actual?.points||actual.points.length!==26||actual.q?.length!==26||names.length!==26||parents?.length!==26)throw Error('liveJoin needs complete actual pose, candidate raw/corrected pose and rig');
 if(frame.slide)throw Error('Slide posture uses its external-root surface solver, not the stair publication join');
 const same=JSON.stringify(actual.points)===JSON.stringify(frame.raw.points)&&JSON.stringify(actual.q)===JSON.stringify(frame.raw.q);
 const contacts=a.contacts||frame.feet.map(f=>f.contact),sameContacts=JSON.stringify(contacts)===JSON.stringify(frame.feet.map(f=>f.contact));
 if(same&&sameContacts)return {frame,identity:true,sourceErrorM:0,pinErrors:frame.feet.map(f=>f.error||0)};
 const source={...actual,axes:actual.q.map(R.toAxes)},pelvis=names.indexOf('pelvis'),delta=sub(frame.pose.points[pelvis],frame.raw.points[pelvis]);
 if(frame.influence===0&&!frame.feet.some(f=>f.contact))return {frame:{...frame,pose:source,raw:source,root:source.points[0].slice(),feet:frame.feet.map((f,side)=>({...f,target:source.points[names.indexOf(side?'foot_r':'foot_l')].slice(),contact:null,error:0}))},identity:false,sourceErrorM:Math.max(...source.points.map((p,i)=>length(sub(p,frame.raw.points[i])))),pinErrors:[0,0]};
 let pose={points:source.points.map((p,i)=>i?add(p,delta):p.slice()),q:source.q.map(q=>q.slice()),axes:source.axes};
 const feet=[],pinErrors=[];
 for(let side=0;side<2;side++){
  const leg=K.stableLeg(source,names,side?'R':'L'),planned=frame.feet[side],contact=planned.contact?(contacts[side]||planned.contact):null;
  if(planned.state==='NN'&&!contact){feet.push({...planned,target:pose.points[leg.foot].slice(),contact:null,error:0});pinErrors.push(0);continue;}
  const ids=[leg.pelvis,leg.hip,leg.knee,leg.foot,leg.toe],sameLower=ids.every(j=>JSON.stringify(source.points[j])===JSON.stringify(frame.raw.points[j])&&JSON.stringify(source.q[j])===JSON.stringify(frame.raw.q[j]));
  if(sameLower&&JSON.stringify(contact)===JSON.stringify(planned.contact)){
   for(const j of [leg.hip,leg.knee,leg.foot,leg.toe]){pose.points[j]=frame.pose.points[j].slice();pose.q[j]=frame.pose.q[j].slice();}
   feet.push(planned);pinErrors.push(planned.error||0);continue;
  }
  const corrected=K.stableLeg(frame.pose,names,side?'R':'L');leg.axisLocal=corrected.axisLocal;leg.poleLocal=corrected.poleLocal;
  let rotation={footQ:frame.pose.q[leg.foot],toeQ:frame.pose.q[leg.toe]},target;
  if(contact){
   const localPoint=contact.localPoint||rotate(qinv(frame.pose.q[leg.foot]),sub(planned.contact.point,frame.pose.points[leg.foot]));
   target=sub(contact.point,rotate(rotation.footQ,localPoint));
  }else target=add(source.points[leg.foot],sub(frame.pose.points[leg.foot],frame.raw.points[leg.foot]));
  pose=K.solve(pose,leg,target,parents,rotation);
  if(!contact){
   // Transfer ankle articulation in calf space after solving the current knee,
   // rather than preserving an obsolete absolute angle from a predicted calf.
   const correction=qm(qm(qinv(frame.pose.q[leg.knee]),frame.pose.q[leg.foot]),qinv(qm(qinv(frame.raw.q[leg.knee]),frame.raw.q[leg.foot])));
   rotation.footQ=qm(pose.q[leg.knee],qm(correction,qm(qinv(source.q[leg.knee]),source.q[leg.foot])));
   const toeCorrection=qm(qm(qinv(frame.pose.q[leg.foot]),frame.pose.q[leg.toe]),qinv(qm(qinv(frame.raw.q[leg.foot]),frame.raw.q[leg.toe])));
   rotation.toeQ=qm(rotation.footQ,qm(toeCorrection,qm(qinv(source.q[leg.foot]),source.q[leg.toe])));
   pose=K.solve(pose,leg,target,parents,rotation);
  }
  const error=length(sub(pose.points[leg.foot],target)),valid=!!contact&&error<.005;
  const pinError=contact?length(sub(add(pose.points[leg.foot],rotate(pose.q[leg.foot],contact.localPoint||rotate(qinv(frame.pose.q[leg.foot]),sub(planned.contact.point,frame.pose.points[leg.foot])))),contact.point)):0;
  pinErrors.push(pinError);feet.push({...planned,target,error,contact:valid?contact:null,state:contact&&!valid?'REACH':planned.state});
 }
 pose.points[0]=source.points[0].slice();
 pose.axes=pose.q.map(R.toAxes);
 return {frame:{...frame,pose,raw:source,feet,root:source.points[0].slice()},identity:false,sourceErrorM:Math.max(...source.points.map((p,i)=>length(sub(p,frame.raw.points[i])))),pinErrors};
}
function covered(a,result){
 const c=a.coverage;if(!c)return true;
 if(!c.center?.every(Number.isFinite)||c.center.length!==3||!c.extent?.every(x=>Number.isFinite(x)&&x>0)||c.extent.length!==3||c.axes?.length!==3||c.axes.some(v=>v.length!==3||!v.every(Number.isFinite)||Math.abs(length(v)-1)>1e-6))throw Error('Invalid native collision query coverage');
 // Include the same32cm neighborhood used by live terrain influence. A
 // covered ankle center alone is insufficient when a toe crosses the query.
 const inside=point=>c.axes.every((axis,i)=>Math.abs(R.dot(sub(point,c.center),axis))+.32<=c.extent[i]);
 const names=a.names||['root',...a.sourceNames];
 for(const input of [a.current,result.frame.pose]){
  const pose={...input,axes:input.axes||input.q.map(R.toAxes)};
  for(const side of ['L','R']){
   const l=K.stableLeg(pose,names,side);
   if(!K.geometry(pose,l).every(offset=>inside(add(pose.points[l.foot],offset))))return false;
  }
 }
 for(const foot of result.frame.feet)if(!inside(foot.target)||(foot.contact&&!inside(foot.contact.point)))return false;
 return true;
}
// This validates the raw NN fallback at the current tick. It is not a terrain
// correction or a replacement for an available plan/recovery/exit transition.
function identity(a){
 const current=a.current,names=a.names||(Array.isArray(a.sourceNames)?['root',...a.sourceNames]:null);
 if(!current?.points||current.points.length!==26||current.q?.length!==26||names?.length!==26||a.parents?.length!==26||!current.points.every(v=>v?.length===3&&v.every(Number.isFinite))||!current.q.every(q=>q?.length===4&&q.every(Number.isFinite)))throw Error('liveIdentity needs a complete finite actual pose and rig');
 if(!a.coverage||a.previousFeet?.length!==2||a.previousFeet.some(f=>!f||f.state!=='NN'||f.contact))return {identity:false};
 const pose={...current,axes:current.q.map(R.toAxes)},legs=['L','R'].map(side=>K.stableLeg(pose,names,side));
 const feet=legs.map(l=>({target:pose.points[l.foot],contact:null}));
 if(!covered({...a,current:pose,names},{frame:{pose,feet}}))return {identity:false};
 const terrain=LiveTerrain.create(a.terrain);
 return {identity:terrain.influence(pose,legs,pose.points[0][1],K.geometry)===0};
}
module.exports={join:a=>{const result=join(a);if(a.coverage)result.covered=covered(a,result);return result;},covered,identity};
