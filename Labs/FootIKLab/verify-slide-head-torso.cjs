'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const R=require('./recovery.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js');
const folder=path.resolve(__dirname,'../../Saved/FootIKHeadTorso20261029');
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
function measure(model,names,parents,settings){
 const head=names.indexOf('head'),chest=names.indexOf('spine_05'),pelvis=names.indexOf('pelvis'),joints=J.build(undefined,names,parents);
 const settled=model.frames.filter(f=>f.slide?.blend===1);let maxDownError=0,headStep=0,chestStep=0,chestRange=0,invalid=0,handGap=0,soleGap=0,previous=null,reference=null,downSamples=0;
 for(const f of settled){const p=f.pose,local=R.qm(R.qinv(p.q[pelvis]),p.q[chest]);reference||=local;chestRange=Math.max(chestRange,angle(local,reference));
  if(previous){headStep=Math.max(headStep,angle(p.q[head],previous.pose.q[head]));chestStep=Math.max(chestStep,angle(local,R.qm(R.qinv(previous.pose.q[pelvis]),previous.pose.q[chest])));}
  for(let j=2;j<names.length;j++)if(!joints.diagnose(j,p.q[parents[j]],p.q[j]).withinLimits)invalid++;
  const speed=R.length(f.surface.velocity),elapsed=model.frames.indexOf(f)/120-f.slide.time;
  if(speed>=(settings.slideHeadSpeed??30)&&elapsed>=.65){downSamples++;const forward=R.rotate(p.q[head],[0,-1,0]),neutral=R.rotate(R.qm(p.q[chest],R.qm(R.qinv(joints.reference.q[chest]),joints.reference.q[head])),[0,-1,0]),downAngle=v=>Math.acos(Math.max(-1,Math.min(1,-v[1])))*180/Math.PI;maxDownError=Math.max(maxDownError,Math.abs(downAngle(forward)-.3*downAngle(neutral)));}
  handGap=Math.max(handGap,f.slide.hand.gap);soleGap=Math.max(soleGap,...f.feet.map(x=>Math.abs(x.soleGap)));previous=f;
 }
 assert(downSamples>20&&maxDownError<.01,'Head turns 70% toward world down at selected maximum speed');
 assert(headStep<3&&chestStep<2,'No neck/chest jumps');
 assert(chestRange>4&&chestRange<18,'Visible bounded upper-body motion');
 assert.equal(invalid,0,'All settled slide joints stay within their limits');
 assert(handGap<.004&&soleGap<.004,'Wall contacts retained');
 return {downSamples,maxDownError,headStep,chestStep,chestRange,invalid,handGap,soleGap};
}
(async()=>{
 const reports=[];
 for(const threshold of [2,5]){const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,`snapshots/slide-live-${threshold}.json.gz`))));if(threshold===2)fixture.request.settings.slideHeadSpeed=20;const run=K.decode(fixture.request.source,require('./data/rig.json').parents),{model}=await C.compute(run,fixture.request.settings,async(_,i)=>fixture.response.steps[i]);reports.push({threshold,headMaxSpeed:fixture.request.settings.slideHeadSpeed??30,...measure(model,run.names,run.parents,fixture.request.settings)});}
 const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.resolve(folder,'../FootIKPerf20261029/current-session.gz')))),state=JSON.parse(fs.readFileSync(path.join(folder,'state-before.json'))),run=K.decode(fixture.request.source,require('./data/rig.json').parents);run.totalDuration=fixture.request.totalDuration;
 const session=C.createSession(run,state.settings,async(_,i)=>fixture.steps[i]),{model}=await session.extend(state.settings.trimOut);session.close();
 const before=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(folder,'before.json.gz'))));let lowerDifference=0;
 assert.equal(model.frames.length,before.frames.length);
 for(let i=0;i<model.frames.length;i++){assert.deepEqual(model.frames[i].root,before.frames[i].root,'Root physics unchanged');for(let j=18;j<run.names.length;j++)lowerDifference=Math.max(lowerDifference,R.length(R.sub(model.frames[i].pose.points[j],before.frames[i].pose.points[j])));}
 reports.push({current:true,frames:model.frames.length,rootExact:true,maxLowerPositionChange:lowerDifference,...measure(model,run.names,run.parents,state.settings)});
 fs.writeFileSync(path.join(folder,'after.json.gz'),z.gzipSync(JSON.stringify({names:run.names,parents:run.parents,frames:model.frames})));
 fs.writeFileSync(path.join(folder,'verification.json'),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports));
})().catch(e=>{console.error(e);process.exitCode=1;});
