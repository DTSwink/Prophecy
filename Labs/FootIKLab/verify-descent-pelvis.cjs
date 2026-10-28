/* Actual Run-policy sources at walk/run speeds; offline, no saved-scene writes. */
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const K=require('./footik.js'),H=require('./handoff.js'),R=require('./recovery.js'),S=require('./support.js');
const fixture=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'data/descent-pelvis-fixture.json.gz'))));
const rig=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'))),checks=[],results=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const distance=(a,b)=>R.length(R.sub(a,b));
const close=(a,b)=>typeof a==='number'?Math.abs(a-b)<1e-9:Array.isArray(a)?a.length===b.length&&a.every((x,i)=>close(x,b[i])):Object.keys(a).every(k=>close(a[k],b[k]));
for(const f of fixture.cases){
 const started=performance.now(),run=K.decode(f.data,rig.parents),m=K.prepare(run,f.settings),label=f.gait+' ';
 check(label+'uses the Run checkpoint with a real root window',run.nnRootWindow&&f.data.source.startsWith('Run 181751')&&f.data.provenance.run.sha256==='0f2565ac72c5209153cbd910135209487f9ef8a0e234ed0c6d99df2ff30a299e');
 check(label+'retains the commanded travel speed',Math.abs(m.speed-(f.gait==='walk'?2:5))<1e-5);
 let minimum=0,maximum=0,kick=0,ankleStep=0,kneeStep=0,pinError=0,rootError=0,flatError=0;
 for(let i=0;i<m.frames.length;i++){
  const a=m.frames[i],p=m.frames[Math.max(0,i-1)];
  minimum=Math.min(minimum,a.pelvisOffset);maximum=Math.max(maximum,a.pelvisOffset);
  rootError=Math.max(rootError,distance(a.root,a.raw.points[0]));
  if(i>1)kick=Math.max(kick,Math.abs(a.pelvisOffset-2*p.pelvisOffset+m.frames[i-2].pelvisOffset)*m.fps);
  for(let side=0;side<2;side++){
   const l=S.leg(a.raw,run.names,side?'R':'L'),contact=a.feet[side].contact;
   if(i){ankleStep=Math.max(ankleStep,angle(a.pose.q[l.foot],p.pose.q[l.foot]));kneeStep=Math.max(kneeStep,angle(a.pose.q[l.knee],p.pose.q[l.knee]));}
   if(contact)pinError=Math.max(pinError,distance(R.add(a.pose.points[l.foot],R.rotate(a.pose.q[l.foot],contact.localPoint)),contact.point));
  }
  if(a.influence===0)for(let j=0;j<run.names.length;j++)flatError=Math.max(flatError,distance(a.pose.points[j],a.raw.points[j]));
 }
 const offset=m.sample(f.sampleAt/60).pelvisOffset;
 check(label+'reported crouch is less than half its previous depth',Math.abs(offset)<Math.abs(f.beforeSample)*.5);
 check(label+'whole descent stays within12cm below the gait pelvis at400% accent',minimum>-.12&&minimum>f.before.minPelvis*.5);
 check(label+'allows the supported positive half of the descending body arc',maximum>.001);
 check(label+'pelvis velocity changes smoothly',kick<.25&&kick<f.before.maxKick*.15);
 check(label+'does not increase ankle or knee rotation steps',ankleStep<=f.before.ankleStep+1e-5&&kneeStep<=f.before.maxKnee+1e-5);
 check(label+'preserves material heel/toe pivots',pinError<1e-8&&m.metrics.pins.every(n=>n>10));
 check(label+'retains full shoe clearance and leg lengths',m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-5);
 check(label+'does not alter the root ramp or pure NN approach',rootError===0&&flatError===0);
 const plan=H.requestFor(m,run);
 check(label+'NN continuation sees the actual corrected current/history poses',close(plan.request.seeds,f.handoff.request.seeds)&&close(plan.request.roots,f.handoff.request.roots));
 const full=H.apply(m,run,plan,f.handoff.response);
 check(label+'whole recorded NN continuation remains finite',full.frames.every(a=>a.pose.points.flat().every(Number.isFinite)&&a.pose.q.flat().every(Number.isFinite)));
 const wanted=JSON.stringify(full.sample(f.sampleAt/60));full.sample(4.5);full.sample(.1);
 check(label+'scrubbing is deterministic',JSON.stringify(full.sample(f.sampleAt/60))===wanted);
 // The option still controls the accent; neutralising it must not bring the crouch back.
 const neutral=K.prepare(run,{...f.settings,stepAccent:0});
 check(label+'reach correction remains small with the accent disabled',neutral.metrics.maxPelvis<.05);
 results.push({gait:f.gait,frame:f.sampleAt,beforePelvisCm:f.beforeSample*100,pelvisCm:offset*100,rangeCm:[minimum*100,maximum*100],pelvisVelocityChange:kick,ankleStep,kneeStep,pinError,metrics:m.metrics,handoff:full.handoff,elapsedMs:performance.now()-started});
}
const result={passed:true,checks,results};fs.writeFileSync(path.join(__dirname,'snapshots/descent-pelvis-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
