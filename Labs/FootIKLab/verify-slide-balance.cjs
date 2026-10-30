'use strict';
// Recorded policy replies: no live NN, browser state writes or extra workers.
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const R=require('./recovery.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js');
const folder=path.resolve(__dirname,'../../Saved/FootIKBalance20261029');
const {sub,mul,dot,cross,length,unit,rotate,qm,qinv,fromTo}=R;
const perpendicular=(v,n)=>sub(v,mul(n,dot(v,n)));
function measure(names,parents,frames){
 const joints=J.build(undefined,names,parents),ref=joints.reference;let roll=0,step=0,speed=0,acceleration=0,height=-Infinity,invalid=0,last=null,previousVelocity=null;
 const points=[];
 for(const f of frames){
  if(f.slide?.blend!==1){last=null;previousVelocity=null;continue;}
  const side=f.slide.hand.side==='l'?'r':'l',a=names.indexOf('upperarm_'+side),b=a+1,c=a+2,p=f.pose;
  const transform=qm(p.q[parents[a]],qinv(ref.q[parents[a]])),axis=unit(sub(p.points[c],p.points[a]));
  const referenceAxis=unit(sub(ref.points[c],ref.points[a])),referencePole=unit(perpendicular(sub(ref.points[b],ref.points[a]),referenceAxis));
  const expected=rotate(fromTo(rotate(transform,referenceAxis),axis),rotate(transform,referencePole)),actual=unit(perpendicular(sub(p.points[b],p.points[a]),axis));
  roll=Math.max(roll,Math.acos(Math.max(-1,Math.min(1,dot(expected,actual))))*180/Math.PI);
  for(const i of [a,b,c])if(!joints.diagnose(i,p.q[parents[i]],p.q[i]).withinLimits)invalid++;
  const hand=sub(p.points[c],p.points[a]);height=Math.max(height,hand[1]);
  // Parent-relative path removes ballistic travel and torso rocking.
  const local=rotate(qinv(p.q[parents[a]]),hand);points.push(local);
  if(last){const v=mul(sub(local,last.local),120);speed=Math.max(speed,length(v));if(previousVelocity)acceleration=Math.max(acceleration,length(mul(sub(v,previousVelocity),120)));previousVelocity=v;
   for(const i of [a,b,c])step=Math.max(step,length(R.qlog(qm(p.q[i],qinv(last.pose.q[i]))))*180/Math.PI);
  }
  last={local,pose:p};
 }
 const mean=mul(points.reduce((a,b)=>R.add(a,b),[0,0,0]),1/points.length),range=points.reduce((r,p)=>r.map((v,i)=>Math.max(v,Math.abs(p[i]-mean[i]))),[0,0,0]);
 assert.equal(invalid,0,'Free shoulder, hinge elbow and wrist remain within Jolt limits');
 assert(roll<1,'Elbow plane remains aligned with transported neutral, not the wall');
 assert(height<-.35,'Balancing hand remains below shoulder');
 assert(step<5,'No sudden upper-arm twist or elbow snap after entry');
 // Short speed bursts traverse the same orbit more quickly.
 assert(speed<1.5&&acceleration<22,`Bounded orbit velocity/acceleration: ${speed} m/s, ${acceleration} m/s²`);
 assert(range.filter(v=>v>.04).length>=2,'Hand circles in at least two dimensions');
 return {rollDegrees:roll,maxStepDegrees:step,maxSpeed:speed,maxAcceleration:acceleration,highestHand:height,halfRanges:range,invalid};
}
(async()=>{
 const reports=[];
 for(const threshold of [2,5]){
  const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,`snapshots/slide-live-${threshold}.json.gz`))));
  const run=K.decode(request.source,require('./data/rig.json').parents),{model}=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);
  reports.push({threshold,...measure(run.names,run.parents,model.frames)});
 }
 if(fs.existsSync(path.join(folder,'before.json.gz'))){
  const record=JSON.parse(z.gunzipSync(fs.readFileSync(path.resolve(__dirname,'../../Saved/FootIKPerf20261029/current-session.gz'))));
  const state=JSON.parse(fs.readFileSync(path.join(folder,'state-before.json'))),run=K.decode(record.request.source,require('./data/rig.json').parents);run.totalDuration=record.request.totalDuration;
  const session=C.createSession(run,state.settings,async(_,i)=>record.steps[i]),{model}=await session.extend(state.settings.trimOut);session.close();
  const before=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(folder,'before.json.gz'))));
  assert.equal(model.frames.length,before.frames.length);
  for(let i=0;i<model.frames.length;i++){
   const a=model.frames[i],b=before.frames[i];assert.deepEqual(a.root,b.root,'Exact unchanged root path');
   for(let j=0;j<run.names.length;j++)if(!a.slide||j<2||/^(thigh|calf|foot|ball)_/.test(run.names[j])){
    assert.deepEqual(a.pose.points[j],b.pose.points[j],'Root/pelvis/leg points are unchanged');assert.deepEqual(a.pose.q[j],b.pose.q[j],'Root/pelvis/leg rotations are unchanged');
   }
  }
  reports.push({current:true,frames:model.frames.length,lowerBodyAndRootExact:true,...measure(run.names,run.parents,model.frames)});
  fs.writeFileSync(path.join(folder,'after.json.gz'),z.gzipSync(JSON.stringify({names:run.names,parents:run.parents,frames:model.frames})));
 }
 fs.writeFileSync(path.join(__dirname,'snapshots/slide-balance-verification.json'),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports));
})().catch(e=>{console.error(e);process.exitCode=1;});
