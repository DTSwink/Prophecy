'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs');
const root=path.resolve(__dirname,'../..'),directory=path.join(root,'Saved/Diagnostics/FootIKPort20261030');
if(!process.argv.includes('--normal'))try{const os=require('node:os');os.setPriority(0,os.constants.priority.PRIORITY_BELOW_NORMAL);}catch{}
const fields=f=>JSON.parse(JSON.stringify({pose:{points:f.pose.points,q:f.pose.q},root:f.root,feet:f.feet,pelvisOffset:f.pelvisOffset,influence:f.influence}));
async function main(){
 const reports=[];
 for(const name of (process.argv.includes('--boundary-only')?[]:['walk-stairs','run-stairs','walk-down','run-down'])){
  const input=JSON.parse(fs.readFileSync(path.join(directory,name+'.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,name+'.expected.json'))),start=performance.now();
  const planner=P.create({...input,handoff:false});const result=await planner.plan();assert(result.ready);
  for(let i=0;i<expected.frames.length;i++)assert.deepEqual(fields(planner.commit(i)),fields(expected.frames[i]),name+' tick'+i);
  const before=planner.status;await planner.plan();assert.equal(planner.status.plans,before.plans);assert.equal(planner.status.inferences,0);
  reports.push({name,frames:expected.frames.length,maxPositionErrorM:0,policyCalls:0,plans:planner.status.plans,cacheHits:planner.status.cacheHits,planMilliseconds:planner.status.planMilliseconds,verificationMilliseconds:performance.now()-start});
  planner.cancel();assert.equal(planner.status.retainedFrames,0);assert.throws(()=>planner.commit());
 }
 const input=JSON.parse(fs.readFileSync(path.join(directory,'walk-stairs.input.json'))),planner=P.create({...input,handoff:false});await planner.plan();
 for(let i=0;i<=160;i++)planner.commit(i);
 const prefix=Array.from({length:161},(_,i)=>JSON.stringify(planner.frame(i))),changed=structuredClone(input.source);
 // A deliberate changed future tail changes an active footprint. This must be
 // surfaced as an unsafe boundary, never silently rewrite accepted contacts.
 for(let i=41;i<changed.poses.length;i++){
  const delta=(i-40)/30*.8;changed.roots[i][2]+=delta;
  for(const point of changed.poses[i].points)point[2]+=delta;
 }
 const update=await planner.plan({source:changed});
 for(let i=planner.status.baseTick;i<=160;i++)assert.equal(JSON.stringify(planner.frame(i)),prefix[i]);
 const future=Array.from({length:changed.poses.length*4-3-161},(_,i)=>planner.frame(i+161)).filter(Boolean);
 const report={fixedFutureExact:reports.length===4,reports,changedFuture:{ready:update.ready,continuity:update.continuity,prefixPreserved:true,maxFuturePenetrationM:Math.max(0,...future.flatMap(f=>f.feet.map(x=>x.penetration||0))),maxFutureReachErrorM:Math.max(0,...future.flatMap(f=>f.feet.map(x=>x.error||0)))},note:'Exact fixed-future K planner plus opt-in material contact/trajectory boundary constraints. Synthetic changed-future source is a structural test, not a real NN or visual-quality signoff.'};
 fs.writeFileSync(path.join(directory,'live-planned-stairs.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
