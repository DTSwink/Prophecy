/* Source-vs-IK motion regression with the real solver active; no state/UI writes. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const K=require('./footik.js'),F=require('./surface.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(path.join(__dirname,p),'utf8')),rig=read('data/rig.json'),saved=read('snapshots/flat-rollout-current-state.json');
(async()=>{
 const s=saved.settings,response=await fetch('http://127.0.0.1:8890/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'direction',policy:'run',gait:s.gait,duration:5,phase:s.phase,direction:s.direction,rootYawSpeed:s.rootYawSpeed,rootYawStart:s.rootYawStart,rootYawStop:s.rootYawStop})});
 assert(response.ok);const current=await response.json();assert(!current.error,current.error);
 fs.writeFileSync(path.join(__dirname,'snapshots/flat-rollout-corrected-source.json'),JSON.stringify(current));
 const results=[];
 for(const [label,data] of [['supplied',read('snapshots/model-viewer-walkf-source.json')],['current',current]]){
  const run=K.decode(data,rig.parents),origin=run.poses[0].points[0];
  for(const approach of ['toward','parallel'])for(const enabled of [true,false])for(const deleteFloorFrame of [-1,0,55]){
   const model=F.prepare(run,{...s,slopeAngle:0,approach,enabled,deleteFloorFrame});
   for(let i=0;i<model.frames.length;i++){
    const f=model.frames[i];
    assert(!f.nn&&!f.surface.authored);assert.equal(f.influence,1);
    assert(f.feet.every(foot=>foot.state!=='NN'));
    assert(f.pose.points.flat().every(Number.isFinite));
    if(i+1<model.frames.length){
     const a=f.surface,b=model.frames[i+1].surface;
     const velocity=R.add(R.add(a.velocity,R.mul(a.acceleration,1/120)),a.collisionImpulse);
     assert(R.length(R.sub(b.velocity,velocity))<1e-9);
    }
   }
   if(enabled)assert(model.metrics.contactFrames>0,'terrain contacts remain active at zero incline');
   results.push({label,approach,enabled,deleteFloorFrame,activeFrames:model.frames.length,contactFrames:model.metrics.contactFrames});
  }
 }
 // A smooth gait is allowed to bend quickly. Bound only the EXTRA motion
 // introduced by IK, comparing each displayed60Hz frame with its own NN input.
 const flex=(p,l)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p.points[l.knee],p.points[l.hip])),R.unit(R.sub(p.points[l.foot],p.points[l.knee]))))))*180/Math.PI;
 const motion=[];
 for(const [label,data] of [['supplied',read('snapshots/model-viewer-walkf-source.json')],['current',current]]){
  const run=K.decode(data,rig.parents),model=F.prepare(run,{...s,slopeAngle:0}),rows=[];
  for(let frame=1;frame<=run.duration*60;frame++)for(const side of ['L','R']){
   const f=model.sample(frame/60),prev=model.sample((frame-1)/60),l=S.leg(f.raw,run.names,side),actual=Math.abs(flex(f.pose,l)-flex(prev.pose,l)),raw=Math.abs(flex(f.raw,l)-flex(prev.raw,l));
   const kneeError=R.length(R.sub(R.sub(f.pose.points[l.knee],f.pose.points[l.hip]),R.sub(f.raw.points[l.knee],f.raw.points[l.hip])));
   rows.push({frame,side,actual,raw,added:actual-raw,kneeError});
  }
  const maxStep=Math.max(...rows.map(r=>r.actual)),maxAddedStep=Math.max(...rows.map(r=>r.added)),maxKneeError=Math.max(...rows.map(r=>r.kneeError));
  assert(maxStep<9,`${label}: no extra large knee kick`);assert(maxAddedStep<4,`${label}: IK cannot add an abrupt bend to a slow NN knee`);assert(maxKneeError<.07);
  assert(model.metrics.maxContactDrift<1e-8&&model.metrics.maxReachError<1e-7&&model.metrics.maxPenetration<1e-4);
  if(model.frames[109].feet.some(f=>f.contact?.surface==='entry'))assert(model.events.some(e=>e.type==='support-transfer'),'coincident remaining surface preserves an existing pin at deletion');
  motion.push({label,maxStep,maxAddedStep,maxKneeError,contactFrames:model.metrics.contactFrames,checkedFrames:run.duration*60});
 }
 // Missing finite ground and explicitly unsupported/gravity-driven motion
 // must never be silently turned back into authored motion.
 const run=K.decode(current,rig.parents);
 assert(!F.prepare(run,{...s,slopeAngle:0},{support:false}).frames[0].nn);
 const displaced={...run,poses:run.poses.map((p,i)=>({...p,points:p.points.map(v=>R.add(v,[i*.5,0,0]))}))};
 assert(!F.prepare(displaced,{...s,slopeAngle:0}).frames[0].nn);
 fs.writeFileSync(path.join(__dirname,'snapshots/flat-rollout-verification.json'),JSON.stringify({passed:true,results,motion},null,2));
 console.log(JSON.stringify({passed:true,cases:results.length,activeFrames:results.reduce((a,b)=>a+b.activeFrames,0),motion}));
})().catch(e=>{console.error(e);process.exitCode=1;});
