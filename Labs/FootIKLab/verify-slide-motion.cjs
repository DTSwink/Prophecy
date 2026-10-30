const fs=require('fs'),z=require('zlib'),assert=require('assert/strict');
const R=require('./recovery.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),S=require('./support.js'),J=require('./slide-joints.js');
(async()=>{
 const reports=[];
 for(const threshold of [2,5]){
  const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(`snapshots/slide-live-${threshold}.json.gz`)));
  const run=K.decode(request.source,require('./data/rig.json').parents),joints=J.build(undefined,run.names,run.parents),{model}=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);
  const start=model.frames.findIndex(f=>f.slide),ready=model.frames.filter(f=>f.slide?.blend===1),indices=run.names.map((n,i)=>i>=2?i:-1).filter(i=>i>=0);
  let invalid=[],handGap=0,soleGap=0,penetration=0,boneError=0,hingeError=0,maxStep=0,entryStep=0,transitionExcess=0,transitionLimbExcess=0,freeHeight=-Infinity;
  const initialError={};
  const ranges={};
  for(let i=start;i<model.frames.length;i++){
   const f=model.frames[i],p=f.pose;
   for(const j of indices){const d=joints.diagnose(j,p.q[run.parents[j]],p.q[j]);
    if(f.slide.blend===1){if(!d.withinLimits)invalid.push({frame:i/2,bone:run.names[j],...d});hingeError=Math.max(hingeError,d.hingeError||0);}
    const correction=joints.project(j,p.q[run.parents[j]],p.q[j]).correctionRad;
    if(i===start)initialError[j]=correction;transitionExcess=Math.max(transitionExcess,correction-initialError[j]);
    if(/^(foot|ball|hand|lowerarm)_/.test(run.names[j]))transitionLimbExcess=Math.max(transitionLimbExcess,correction-initialError[j]);
   }
   for(let j=2;j<run.names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(R.sub(p.points[j],p.points[run.parents[j]]))-R.length(R.sub(model.frames[start].pose.points[j],model.frames[start].pose.points[run.parents[j]]))));
   if(i>0)for(const j of indices){const angle=R.length(R.qlog(R.qm(p.q[j],R.qinv(model.frames[i-1].pose.q[j]))))*180/Math.PI;if(i===start)entryStep=Math.max(entryStep,angle);else maxStep=Math.max(maxStep,angle);}
   penetration=Math.max(penetration,...f.feet.map(x=>x.penetration));
   if(f.slide.blend===1){handGap=Math.max(handGap,f.slide.hand.gap);soleGap=Math.max(soleGap,...f.feet.map(x=>Math.abs(x.soleGap)));
    for(const side of ['l','r']){const h=run.names.indexOf('hand_'+side),a=run.names.indexOf('upperarm_'+side),relative=R.sub(p.points[h],p.points[a]);ranges[side]||={min:relative.slice(),max:relative.slice()};relative.forEach((v,k)=>{ranges[side].min[k]=Math.min(ranges[side].min[k],v);ranges[side].max[k]=Math.max(ranges[side].max[k],v);});if(side!==f.slide.hand.side)freeHeight=Math.max(freeHeight,relative[1]);}
   }
  }
  const report={threshold,start:start/2,invalid:invalid.slice(0,8),invalidCount:invalid.length,transitionExcess,transitionLimbExcess,freeHeight,handGap,soleGap,penetration,boneError,hingeError,maxStep,entryStep,ranges,metrics:model.metrics};reports.push(report);
  fs.writeFileSync(`snapshots/slide-joints-model-${threshold}.json`,JSON.stringify({names:run.names,parents:run.parents,frames:model.frames}));
 }
 fs.writeFileSync('snapshots/slide-joints-motion.json',JSON.stringify(reports,null,2));console.log(JSON.stringify(reports));
 if(process.env.SLIDE_DIAGNOSTIC_ONLY!=='1')for(const r of reports){assert.equal(r.invalidCount,0,'All settled slide joints within Jolt limits');assert(r.transitionLimbExcess<1e-7,'Incoming ankle/wrist/elbow violations only decay during blend');assert(r.freeHeight<-.35,'Free hand hangs below shoulder');assert(r.boneError<1e-8,'Fixed bone lengths');assert(r.penetration<1e-5,'No foot penetration');assert(r.handGap<.004&&r.soleGap<.004,'Actual sliding contacts');assert(r.maxStep<20,'Bounded adjacent-frame joint movement after incoming NN frame');assert(Object.values(r.ranges).every(v=>R.length(R.sub(v.max,v.min))>.01),'Secondary motion continues after blend');}
})().catch(e=>{console.error(e);process.exitCode=1});
