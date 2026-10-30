const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const K=require('./footik.js'),F=require('./surface.js'),C=require('./surface-coupling.js'),R=require('./recovery.js');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,'data/wall-frame-run-fixture.json.gz'))));
(async()=>{
 fixture.request.settings={...fixture.request.settings,pelvisCloser:0};
 const {request,response}=fixture,parents=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'))).parents;
 const run=K.decode(request.source,parents),checks=[],check=(name,value)=>{assert(value,name);checks.push(name);};
 const {model,steps}=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);
 check('149 recurrent updates follow the initial history pair',steps.length===149);
 check('policy stream agrees with existing native recurrent implementation',response.referenceError<1e-5);
 check('all root windows agree with the original training encoder',response.featureError<1e-6);
 check('all body poses and actual root velocities are finite',model.frames.every(f=>[...f.pose.points.flat(),...f.raw.q.flat(),...f.surface.velocity].every(Number.isFinite)));
 const virtual=[[0,0,0]];
 for(let i=1;i<model.frames.length;i++){
  const a=model.frames[i-1],b=model.frames[i];
  virtual.push(R.add(virtual[i-1],C.transport({base:a.root,surfaceQ:a.surface.gaitRotation},{base:b.root,surfaceQ:b.surface.gaitRotation})));
 }
 let historyError=0,replayError=0;
 for(const w of model.coupling.windows){
  const i=w.frame*2,expected=R.sub(virtual[i],virtual[i-4]);historyError=Math.max(historyError,R.length(R.sub(expected,w.delta)));
  const original=response.diagnostics.coupling.windows.find(x=>x.frame===w.frame);replayError=Math.max(replayError,R.length(R.sub(original.root,w.root)),R.length(R.sub(original.velocity,w.velocity)));
 }
 check('every history delta comes from the actual physical root',historyError<1e-10);
 check('replay reproduces the roots used during live inference',replayError<1e-8);
 check('future window has all eight positions and upcoming yaws',model.coupling.windows.every(w=>w.future.length===8&&w.futureYaw.length===8));
 check('NN sees the initial approach',model.coupling.windows[0].delta[2]>0);
 check('NN sees near-stationary travel around the reversal',model.coupling.windows.some(w=>Math.abs(w.delta[2]*30)<.3));
 check('NN sees reversed travel instead of the old positive command',model.coupling.windows.find(w=>w.frame===144).delta[2]<0);
 const f=model.sample(143/60),w=model.coupling.windows.find(w=>w.frame===144),heading=K.rootHeading(run,144/60,request.settings,model.speed);
 check('current NN travel is forward relative to final facing',R.dot(heading,w.delta)>0);
 check('real root remains gravity-driven',f.surface.velocity[1]<-3);
 check('shoe collision and reach constraints remain active',model.metrics.maxPenetration<1e-5&&model.metrics.maxReachError<1e-5);
 check('material contacts do not drift',model.metrics.maxContactDrift<1e-8&&model.metrics.wallContactFrames>0);
 check('low-speed steep pins still cancel',model.frames.filter(f=>!f.surface.pinsAllowed).every(f=>f.feet.every(x=>!x.contact)));
 check('initial authored phase is retained',R.length(R.sub(model.frames[0].raw.points[1],run.poses[0].points[1]))<1e-8);
 // Prediction must use copies: generating extra futures cannot change physics.
 // Interactive simulation requires its actual pose/contact replies. Wrap the
 // ordinary coupled replay so only the number of extra forecasts differs.
 const originalSimulate=F.simulate;let forecastReplay;
 F.simulate=function*(...args){const g=originalSimulate(...args);let next=g.next();while(!next.done){if(!next.value.checkpoint){next.value.forecast(40);next.value.forecast(7);}const reply=yield next.value;next=g.next(reply);}return next.value;};
 try{forecastReplay=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);}finally{F.simulate=originalSimulate;}
 check('forecasting cannot mutate actual root/foot history',JSON.stringify(model.frames)===JSON.stringify(forecastReplay.model.frames));
 const report={passed:true,checks,historyError,replayError,frame143:{velocity:f.surface.velocity,nnSpeed:w.delta.map(v=>v*30),heading},metrics:model.metrics,workerSeconds:response.seconds,policySeconds:response.policySeconds};
 fs.writeFileSync(path.join(__dirname,'snapshots/surface-coupling-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
