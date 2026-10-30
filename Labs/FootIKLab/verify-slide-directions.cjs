'use strict';
// Sequential replay of independently generated native NN fixtures. This script
// never starts inference, edits live settings, or substitutes a rotated gait.
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib');
const K=require('./footik.js'),R=require('./recovery.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js');
const parents=require('./data/rig.json').parents;
const DEG=180/Math.PI,DT=1/120;
const read=p=>JSON.parse(p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p,'utf8'));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*DEG;
const distance=(a,b)=>R.length(R.sub(a,b));
function recordTop(list,value,frame,bone,extra){
 if(!Number.isFinite(value))return;
 list.push({value,frame,bone,...extra});list.sort((a,b)=>b.value-a.value);if(list.length>12)list.length=12;
}
function segmentDistance(p1,q1,p2,q2){
 const d1=R.sub(q1,p1),d2=R.sub(q2,p2),r=R.sub(p1,p2),a=R.dot(d1,d1),e=R.dot(d2,d2),f=R.dot(d2,r),clamp=x=>Math.max(0,Math.min(1,x));let s=0,t=0;
 if(a<=1e-12&&e<=1e-12)return distance(p1,p2);
 if(a<=1e-12)t=clamp(f/e);
 else{const c=R.dot(d1,r);if(e<=1e-12)s=clamp(-c/a);else{const b=R.dot(d1,d2),den=a*e-b*b;s=den?clamp((b*f-c*e)/den):0;t=(b*s+f)/e;if(t<0){t=0;s=clamp(-c/a);}else if(t>1){t=1;s=clamp((b-c)/a);}}}
 return distance(R.add(p1,R.mul(d1,s)),R.add(p2,R.mul(d2,t)));
}
async function replay(fixture,overrides){
 const request=fixture.request,run=K.decode(request.source,parents),settings={...request.settings,...overrides};let consumed=0;
 const session=C.createSession(run,settings,async(_,i)=>{const reply=fixture.response.steps[i];if(!reply)throw Error(`Recorded policy stream exhausted at ${i}; regenerate this independently configured case`);consumed++;return reply;});
 try{await session.extend(request.endTime??5);return {run,settings,model:session.model,policyReplies:consumed};}finally{session.close();}
}
function measure({run,settings,model,policyReplies},name){
 const names=run.names,joints=J.build(undefined,names,parents),frames=model.frames,pelvis=names.indexOf('pelvis');
 const starts=frames.map((f,i)=>f.slide&&!frames[i-1]?.slide?i:-1).filter(i=>i>=0);
 const report={name,settings:{gait:settings.gait,direction:settings.direction,phase:settings.phase,slopeAngle:settings.slopeAngle,approach:settings.approach,rootYawSpeed:settings.rootYawSpeed,slideBlend:settings.slideBlend},source:{direction:run.direction,commandSpeed:run.directionMeta?.commandSpeed,source:run.source},frameCount:frames.length,policyReplies,slideStarts:starts.map(i=>i/2),finite:true,boneErrorM:0,settledInvalid:[],entryAddedLimitDeg:[],jointStepsDeg:[],kneeStepsDeg:[],ankleStepsDeg:[],preSlideKneeStepsDeg:[],footSpeedMps:[],footAccelerationMps2:[],pelvisSpeedMps:[],maxPenetrationM:0,maxSettledSoleGapM:0,maxSettledHandGapM:0,maxClaimedSoleGapM:0,maxClaimedHandGapM:0,detachedFootTicks:0,detachedHandTicks:0,minOppositeLegCenterlineM:null,transitions:[]};
 const bones=names.map((_,i)=>i).filter(i=>i>=2),legNames=['thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'],legIndex=legNames.map(n=>names.indexOf(n));
 let entry=-1,initialError={},initialLengths=[];
 for(let i=0;i<frames.length;i++){
  const f=frames[i],p=f.pose;
  if(!p.points.every(v=>v.every(Number.isFinite))||!p.q.every(v=>v.every(Number.isFinite)))report.finite=false;
  if(!f.slide){
   if(i>0&&!frames[i-1].slide)for(const j of legIndex.filter(j=>names[j].startsWith('calf'))){const step=angle(p.q[j],frames[i-1].pose.q[j]);recordTop(report.preSlideKneeStepsDeg,step,i/2,names[j],{rawStep:angle(f.raw.q[j],frames[i-1].raw.q[j])});}
   continue;
  }
  if(!frames[i-1]?.slide){entry=i;initialError=Object.fromEntries(bones.map(j=>[j,joints.project(j,p.q[parents[j]],p.q[j]).correctionRad]));initialLengths=p.points.map((v,j)=>j?distance(v,p.points[parents[j]]):0);}
  for(const j of bones){
   report.boneErrorM=Math.max(report.boneErrorM,Math.abs(distance(p.points[j],p.points[parents[j]])-initialLengths[j]));
   const diagnosis=joints.diagnose(j,p.q[parents[j]],p.q[j]);
   if(f.slide.blend===1&&(f.slide.legBlend??1)===1&&(f.slide.pelvisBlend??1)===1&&!diagnosis.withinLimits&&report.settledInvalid.length<20)report.settledInvalid.push({frame:i/2,bone:names[j],...diagnosis});
   const excess=(joints.project(j,p.q[parents[j]],p.q[j]).correctionRad-initialError[j])*DEG;
   if(excess>1e-5)recordTop(report.entryAddedLimitDeg,excess,i/2,names[j]);
   if(i>entry){const step=angle(p.q[j],frames[i-1].pose.q[j]);recordTop(report.jointStepsDeg,step,i/2,names[j]);if(names[j].startsWith('calf'))recordTop(report.kneeStepsDeg,step,i/2,names[j]);if(names[j].startsWith('foot'))recordTop(report.ankleStepsDeg,step,i/2,names[j]);}
  }
  for(const foot of f.feet){report.maxPenetrationM=Math.max(report.maxPenetrationM,foot.penetration||0);if(f.slide.blend===1&&(f.slide.legBlend??1)===1&&(f.slide.pelvisBlend??1)===1){const gap=Math.abs(foot.soleGap||0);report.maxSettledSoleGapM=Math.max(report.maxSettledSoleGapM,gap);if(foot.slideContact)report.maxClaimedSoleGapM=Math.max(report.maxClaimedSoleGapM,gap);else report.detachedFootTicks++;}}
  if(f.slide.blend===1&&(f.slide.legBlend??1)===1&&(f.slide.pelvisBlend??1)===1){const gap=Math.abs(f.slide.hand?.gap||0);report.maxSettledHandGapM=Math.max(report.maxSettledHandGapM,gap);if(f.slide.hand?.touching)report.maxClaimedHandGapM=Math.max(report.maxClaimedHandGapM,gap);else report.detachedHandTicks++;}
  const rel=j=>R.sub(p.points[j],p.points[pelvis]);
  for(const j of legIndex.filter(j=>names[j].startsWith('foot'))){
   if(i>entry){const previous=frames[i-1].pose,prevRel=R.sub(previous.points[j],previous.points[pelvis]),velocity=R.mul(R.sub(rel(j),prevRel),1/DT);recordTop(report.footSpeedMps,R.length(velocity),i/2,names[j]);
    if(i>entry+1){const old=frames[i-2].pose,oldRel=R.sub(old.points[j],old.points[pelvis]),prevVelocity=R.mul(R.sub(prevRel,oldRel),1/DT);recordTop(report.footAccelerationMps2,R.length(R.sub(velocity,prevVelocity))/DT,i/2,names[j]);}}
  }
  if(i>entry){const normal=f.surface.normal,prev=frames[i-1],v=R.sub(R.sub(p.points[pelvis],f.surface.mass),R.sub(prev.pose.points[pelvis],prev.surface.mass));recordTop(report.pelvisSpeedMps,Math.abs(R.dot(v,normal))/DT,i/2,'pelvis');}
  for(const a of [[0,1],[1,2]])for(const b of [[3,4],[4,5]]){const d=segmentDistance(p.points[legIndex[a[0]]],p.points[legIndex[a[1]]],p.points[legIndex[b[0]]],p.points[legIndex[b[1]]]);if(report.minOppositeLegCenterlineM===null||d<report.minOppositeLegCenterlineM)report.minOppositeLegCenterlineM=d;}
 }
 for(const start of starts){
  let end=start;while(end+1<frames.length&&frames[end].slide?.blend<1&&frames[end+1].slide)end++;
  const samples=frames.slice(start,end+1).map((f,k)=>{const point=f.slide.hand?.point||f.surface.mass,n=f.surface.normal;return {frame:(start+k)/2,blend:f.slide.blend,distance:R.dot(R.sub(f.pose.points[pelvis],point),n),relativeRoot:R.dot(R.sub(f.pose.points[pelvis],f.surface.mass),n)};});
  const a=samples[0],b=samples.at(-1);let overshoot=0,undershoot=0;
  for(const s of samples){overshoot=Math.max(overshoot,s.distance-Math.max(a.distance,b.distance));undershoot=Math.max(undershoot,Math.min(a.distance,b.distance)-s.distance);}
  report.transitions.push({start:start/2,end:end/2,startDistanceM:a.distance,endDistanceM:b.distance,awayOvershootM:overshoot,towardOvershootM:undershoot,samples});
 }
 // Distinguish a solver-authored pelvis detour from legitimate root inertia.
 report.maxSlidePelvisDetourM=0;let carried=null;
 for(const f of frames){
  if(!f.slide){carried=null;continue;}
  carried??=f;
  const plane=require('./surface.js').createTerrain(settings).allSurfaces.find(p=>p.id===f.slide.surface);
  const gap=plane?R.dot(R.sub(carried.pose.points[pelvis],plane.closest(carried.pose.points[pelvis])),plane.normal):0;
  const shift=plane?R.mul(plane.normal,-Math.min((settings.slideCloser||0)/100,Math.max(0,gap-.15))*(f.slide.pelvisBlend??f.slide.blend)):[0,0,0];
  const expected=R.add(R.add(carried.pose.points[pelvis],R.sub(f.root,carried.root)),shift);
  report.maxSlidePelvisDetourM=Math.max(report.maxSlidePelvisDetourM,distance(f.pose.points[pelvis],expected));
 }
 report.failures=[];
 if(!report.finite)report.failures.push('nonfinite pose');
 if(report.boneErrorM>1e-6)report.failures.push('changing segment lengths');
 if(report.settledInvalid.length)report.failures.push('settled joint limits');
 if(report.entryAddedLimitDeg.some(x=>x.bone.startsWith('thigh_')&&x.value>.01))report.failures.push('entry adds a hip-limit violation');
 if(report.maxSlidePelvisDetourM>1e-6)report.failures.push('slide solver adds a pelvis detour');
 if(report.maxPenetrationM>.005)report.failures.push('foot penetration > 5 mm');
 // Outward inertial velocity may legitimately carry the ballistic root out of
 // reach. Do not demand contacts that the pose solver explicitly released.
 if(report.maxClaimedSoleGapM>.02)report.failures.push('claimed sole contact gap > 2 cm');
 if(report.maxClaimedHandGapM>.02)report.failures.push('claimed palm contact gap > 2 cm');
 // These are review flags, not a claim that a scalar threshold proves humanity.
 report.review=[];
 if(!starts.length)report.review.push('Slide not reached in recorded span; inspect root condition');
 if(report.transitions.some(t=>t.awayOvershootM>.03))report.review.push('pelvis outward excursion > 3 cm');
 if(report.jointStepsDeg[0]?.value>12)report.review.push('joint step > 12 degrees at 120 Hz');
 if(report.footAccelerationMps2[0]?.value>100)report.review.push('foot acceleration > 100 m/s2 relative to pelvis');
 if(report.minOppositeLegCenterlineM!==null&&report.minOppositeLegCenterlineM<.03)report.review.push('opposite leg centerlines within 3 cm');
 return report;
}
async function main(){
 const args=process.argv.slice(2),manifestPath=path.resolve(args.find(x=>!x.startsWith('--'))||path.join(__dirname,'../../Saved/FootIKSlideAudit20261029/cases.json')),manifest=read(manifestPath),base=path.dirname(manifestPath),out=path.resolve(base,manifest.output||'coverage');fs.mkdirSync(out,{recursive:true});const reports=[];
 for(const item of manifest.cases||manifest){
  const fixture=read(path.resolve(base,item.fixture)),result=await replay(fixture,item.overrides),report=measure(result,item.name||path.basename(item.fixture));reports.push(report);
  const safe=report.name.replace(/[^a-zA-Z0-9_-]/g,'-');fs.writeFileSync(path.join(out,safe+'.model.json.gz'),z.gzipSync(JSON.stringify({names:result.run.names,parents,settings:result.settings,frames:result.model.frames}),{level:1}));
  fs.writeFileSync(path.join(out,safe+'.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({name:report.name,entry:report.slideStarts,failures:report.failures,review:report.review,maxJointStep:report.jointStepsDeg[0],pelvis:report.transitions.map(({samples,...v})=>v)}));
 }
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({passed:reports.every(r=>!r.failures.length),reports},null,2));
 if(args.includes('--strict')&&reports.some(r=>r.failures.length))process.exitCode=1;
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1;});
module.exports={replay,measure};
