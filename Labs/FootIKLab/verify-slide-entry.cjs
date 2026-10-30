'use strict';
// Replay exact native NN replies. No new policy process or live settings edits.
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const K=require('./footik.js'),R=require('./recovery.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js');
const folder=path.resolve(__dirname,'../../Saved/FootIKSlideHip20261029'),parents=require('./data/rig.json').parents;
const read=p=>JSON.parse(z.gunzipSync(fs.readFileSync(p)));
async function replay(fixture){
 const {request,response}=fixture,run=K.decode(request.source,parents),session=C.createSession(run,request.settings,async(_,i)=>response.steps[i]);
 await session.extend(request.endTime??5);session.close();return {run,frames:session.model.frames};
}
(async()=>{
 const fixtures=[['reported',read(path.join(folder,'fixture.json.gz'))],['full-gravity',read(path.join(folder,'../FootIKSlideTransitions20261029/gravity100-response.json.gz'))],['later-fall',read(path.join(__dirname,'snapshots/slide-live-5.json.gz'))]],reports=[];
 for(const [name,fixture]of fixtures){
  const {run,frames}=await replay(fixture),joints=J.build(undefined,run.names,parents),first=frames.findIndex(f=>f.slide),initial=frames[first].pose;
  let hipExcess=0,hipStep=0,penetration=0,boneError=0,settledInvalid=0;
  const hips=['thigh_l','thigh_r'].map(n=>run.names.indexOf(n));
  for(let i=first;i<frames.length;i++){
   const f=frames[i];if(!f.slide)continue;
   penetration=Math.max(penetration,...f.feet.map(x=>x.penetration));
   for(const j of hips){
    const error=p=>joints.project(j,p.q[parents[j]],p.q[j]).correctionRad;
    hipExcess=Math.max(hipExcess,error(f.pose)-error(initial));
    if(i>first)hipStep=Math.max(hipStep,R.length(R.qlog(R.qm(f.pose.q[j],R.qinv(frames[i-1].pose.q[j]))))*180/Math.PI);
   }
   for(let j=18;j<26;j++){
    if(f.slide.blend===1&&!joints.diagnose(j,f.pose.q[parents[j]],f.pose.q[j]).withinLimits)settledInvalid++;
    boneError=Math.max(boneError,Math.abs(R.length(R.sub(f.pose.points[j],f.pose.points[parents[j]]))-R.length(R.sub(initial.points[j],initial.points[parents[j]]))));
   }
  }
  const report={name,entry:first/2,hipExcessDegrees:hipExcess*180/Math.PI,hipStepDegrees:hipStep,penetration,boneError,settledInvalid};reports.push(report);
  assert(hipExcess<1e-6,name+': entry must not invent hip-limit violations');assert.equal(settledInvalid,0,name+': settled leg limits');assert(boneError<1e-7,name+': fixed limb lengths');
  if(name==='reported'){
   const before=read(path.join(folder,'before-frames.json.gz'));
   assert(JSON.stringify(frames.slice(0,first))===JSON.stringify(before.slice(0,first)),'Exact serialized pre-slide prefix');
   assert(JSON.stringify(frames.map(f=>f.surface))===JSON.stringify(before.map(f=>f.surface)),'Exact serialized ballistic root');
   assert(hipStep<8,'No thigh snap through the reported transition');assert(penetration<1e-5,'No replacement wall clipping');
   fs.writeFileSync(path.join(folder,'after-frames.json.gz'),z.gzipSync(JSON.stringify(frames)));
  }
 }
 console.log(JSON.stringify(reports));fs.writeFileSync(path.join(folder,'verification.json'),JSON.stringify({passed:true,reports},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
