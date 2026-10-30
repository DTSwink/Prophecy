'use strict';
// Regression for smooth requested contacts producing sideways palm chatter.
// Uses a captured native NN stream: no inference/server/UI mutation.
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const K=require('./footik.js'),C=require('./surface-coupling.js'),R=require('./recovery.js'),J=require('./slide-joints.js');
const directory=path.resolve(__dirname,'../../Saved/FootIKSlideAudit20261029'),fixturePath=process.argv[2]||path.join(directory,'heading-live.fixture.json.gz');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(fixturePath))),parents=require('./data/rig.json').parents,run=K.decode(fixture.request.source,parents),s=K.sanitize(fixture.request.settings),dt=1/120;
function measure(model){
 const frames=model.frames,joints=J.build(undefined,run.names,parents),start=frames.findIndex(f=>f.slide),after=start+Math.ceil((Math.max(s.slideBlend,s.slideLegBlend,s.slidePelvisBlend)+.05)/dt);
 const out={startFrame:after/2,endFrame:(frames.length-1)/2,maxLateralAcceleration:0,maxHandWorldStepDeg:0,maxElbowAcceleration:0,maxPalmGap:0,contactSamples:0,samples:0,invalid:[],rapidReversals:0};
 for(let i=Math.max(2,after);i<frames.length;i++){
  const a=frames[i-2],b=frames[i-1],f=frames[i];if(!a.slide||!b.slide||!f.slide)continue;
  const lateral=R.unit(R.cross([0,1,0],f.surface.normal));
  for(const side of['l','r']){
   const hand=run.names.indexOf('hand_'+side),elbow=run.names.indexOf('lowerarm_'+side),p=(f,k)=>R.sub(f.pose.points[k],f.root),d=R.sub(p(f,hand),p(b,hand)),previous=R.sub(p(b,hand),p(a,hand));
   const velocity=R.dot(d,lateral)/dt,previousVelocity=R.dot(previous,lateral)/dt;
   out.maxLateralAcceleration=Math.max(out.maxLateralAcceleration,Math.abs((velocity-previousVelocity)/dt));
   if(velocity*previousVelocity<0&&Math.min(Math.abs(velocity),Math.abs(previousVelocity))>.2)out.rapidReversals++;
   out.maxHandWorldStepDeg=Math.max(out.maxHandWorldStepDeg,R.length(R.qlog(R.qm(f.pose.q[hand],R.qinv(b.pose.q[hand]))))*180/Math.PI);
   out.maxElbowAcceleration=Math.max(out.maxElbowAcceleration,R.length(R.sub(R.sub(p(f,elbow),p(b,elbow)),R.sub(p(b,elbow),p(a,elbow))))/(dt*dt));
   const receipt=f.slide.hands.find(h=>h.side===side);out.samples++;out.contactSamples+=+receipt.touching;out.maxPalmGap=Math.max(out.maxPalmGap,receipt.gap);
   for(const name of['upperarm_','lowerarm_','hand_']){const k=run.names.indexOf(name+side);if(!joints.diagnose(k,f.pose.q[parents[k]],f.pose.q[k]).withinLimits)out.invalid.push({frame:i/2,bone:name+side});}
  }
 }
 return out;
}
(async()=>{const session=C.createSession(run,s,async(_,i)=>fixture.response.steps[i]);try{
 await session.extend(fixture.request.endTime??s.trimOut??5);
 const report=measure(session.model),oldPath=path.join(directory,'hand-jitter-model.json.gz');
 if(fs.existsSync(oldPath)){const old=JSON.parse(z.gunzipSync(fs.readFileSync(oldPath)));report.before=measure(old);report.maxRootChange=Math.max(...session.model.frames.map((f,i)=>R.length(R.sub(f.root,old.frames[i].root))));}
 fs.writeFileSync(path.join(directory,'hand-continuity-fixed.model.json.gz'),z.gzipSync(JSON.stringify({names:run.names,parents,settings:s,frames:session.model.frames}),{level:1}));
 fs.writeFileSync(path.join(directory,'hand-continuity-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 assert(report.samples>30,'Enough settled slide samples');assert(report.invalid.length===0,'Legal arm joints');
 assert(report.maxLateralAcceleration<25,'No fast alternating sideways palm acceleration');assert(report.maxHandWorldStepDeg<1.5,'No visible palm orientation jumps');
 assert(report.maxElbowAcceleration<85,'No elbow pole chatter');assert(report.rapidReversals===0,'No fast direction reversals');
 assert(report.contactSamples/report.samples>.90&&report.maxPalmGap<.006,'Contact retained with smooth arm motion');
 if(report.maxRootChange!=null)assert(report.maxRootChange<1e-10,'Root trajectory unchanged');
 }finally{session.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
