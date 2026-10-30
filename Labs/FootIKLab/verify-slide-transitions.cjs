'use strict';
// Controlled upward impulses exist only in this VM harness, never in the app.
// Recorded NN covers the original approach; a deterministic pose responder
// checks restart/history plumbing after the impulse, not learned motion quality.
const fs=require('fs'),path=require('path'),vm=require('vm'),z=require('zlib'),assert=require('assert/strict'),{createRequire}=require('module');
const local=createRequire(__filename),K=require('./footik.js'),R=require('./recovery.js'),C=require('./surface-coupling.js');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,'snapshots/slide-live-5.json.gz'))));
const run=K.decode(fixture.request.source,require('./data/rig.json').parents);
function injected(impulses){
 const source=fs.readFileSync(path.join(__dirname,'surface.js'),'utf8'),marker='function begin(time){';assert(source.includes(marker));
 const context={module:{exports:{}},require:local,console,externalVelocity:time=>impulses[Math.round(time*120)]};
 vm.runInNewContext(source.replace(marker,marker+' const injected=externalVelocity(time);if(injected)velocity=injected.slice();'),context);
 const coupling={module:{exports:{}},require:name=>name==='./surface.js'?context.module.exports:local(name),console};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'surface-coupling.js'),'utf8'),coupling);return coupling.module.exports;
}
async function solve(ends){
 const calls=[],api=injected({276:[0,3,0],336:[0,-6,0]});let resumed=false;
 const session=api.createSession(run,fixture.request.settings,async(request,i)=>{
  calls.push(request);resumed||=!!request.reset;
  if(!resumed)return fixture.response.steps[i];
  const source=request.seeds?.[1]||fixture.response.steps.at(-1).pose,root=request.roots[2];
  return {pose:{points:source.points.map(v=>R.add(root,R.sub(v,source.points[0]))),axes:source.axes},pins:[0,0]};
 });
 for(const end of ends)await session.extend(end);session.close();return {model:session.model,calls};
}
(async()=>{
 const {model}=await C.compute(run,fixture.request.settings,async(_,i)=>fixture.response.steps[i]);
 const entry=model.frames.find(f=>f.slide);assert(entry.surface.velocity[1]<=-5);assert(model.frames.filter(f=>f.surface.velocity[1]>0).every(f=>!f.slide));
 const whole=await solve([3.2]),split=await solve([2.3,2.3333333333333335,2.6,3.2]);
 assert.equal(JSON.stringify(whole.model.frames),JSON.stringify(split.model.frames),'Trim extensions preserve entry/exit/re-entry exactly');
 const events=whole.model.events.filter(e=>['slide','slide-exit'].includes(e.type));
 assert.equal(events.filter(e=>e.type==='slide').length,2);assert.equal(events.filter(e=>e.type==='slide-exit').length,1);
 const exit=events.find(e=>e.type==='slide-exit');assert.equal(exit.frame,138);assert(exit.velocity[1]>0);
 assert(whole.calls.filter(r=>r.reset).length===1,'Reseed NN once on ascent');
 const reset=whole.calls.find(r=>r.reset);assert.equal(reset.seeds.length,2);
 for(let i=0;i<2;i++)assert(R.length(R.sub(reset.seeds[i].points[0],reset.roots[i]))<1e-10,'Both history poses use the new root window');
 for(let i=276;i<336;i++){const f=whole.model.frames[i];assert(!f.slide,'Locomotion resumes between slides');assert.equal(f.feet.length,2,'Foot solver resumes');assert(f.pose.points.every(v=>v.every(Number.isFinite)));}
 assert(whole.model.frames[336].slide.blend===0,'Re-entry restarts the pose blend');
 const first=whole.model.frames[276],previous=whole.model.frames[275];
 const maxExitAngle=Math.max(...first.pose.q.map((q,j)=>R.length(R.qlog(R.qm(q,R.qinv(previous.pose.q[j]))))*180/Math.PI));
 assert(maxExitAngle<20,'No instantaneous full-pose jump on exit');
 const report={passed:true,events,maxExitAngle,resumedPolicyCalls:whole.calls.filter(r=>r.reset).length,splitExact:true};
 const folder=path.resolve(__dirname,'../../Saved/FootIKSlideTransitions20261029');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'transitions.json'),JSON.stringify(report,null,2));fs.writeFileSync(path.join(folder,'resume-request.json'),JSON.stringify(reset));fs.writeFileSync(path.join(folder,'initial-request.json'),JSON.stringify(whole.calls[0]));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
