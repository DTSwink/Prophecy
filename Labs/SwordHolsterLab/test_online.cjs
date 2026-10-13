const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const H=require('./holster'),R=require('./recovery'),C=require('./retime'),Playback=require('./sequence');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json');
const settings=sheathe=>({...saved.parameters,...saved.parameters[sheathe?'sheatheBody':'drawBody'],sheathe,noCheat:true,duration:8});
const maxPose=(a,b)=>Math.max(...a.flatMap((p,j)=>[R.length(R.sub(p.p,b[j].p)),H.angle(p.q,b[j].q)]));
const report=[];
// Audit every dynamic input read through reach, slide, head and FK return.
// One static idle authoring reference is followed by exactly the current tick's
// gazed/ungazed samples; no future arrival or guide-frame reads are allowed.
const reads=[],Online=require('./online');
const traced=Online.prepare({...H,motion:(d,k,t,g)=>{reads.push([k,t]);return H.motion(d,k,t,g);}},data,setup,{...settings(true),motion:'run'});
assert.equal(reads.length,1+2*traced.frames.length);
for(let i=0;i<traced.frames.length;i++)for(let j=0;j<2;j++)assert.equal(reads[1+i*2+j][1],i/60);
for(const motion of ['idle','walk','run'])for(const sheathe of [true,false]){
 const options={...settings(sheathe),motion},a=H.prepare(data,setup,options),cutoff=40;
 const changed=structuredClone(data),clip=changed.motions[motion];
 // Keep the entire observed prefix, timestamps and duration identical. Change
 // the future pose radically enough to alter the old future-arrival planner.
 for(let i=Math.floor(cutoff/60*(clip.fps||data.fps))+1;i<clip.frames.length;i++)for(const p of clip.frames[i]){
  p[0]+=35;p[2]+=20;const q=R.qm(R.qexp([.45,-.7,.3]),p.slice(3));p.splice(3,4,...q);
 }
 const b=H.prepare(changed,setup,options);
 for(let i=0;i<=cutoff;i++){
  assert(maxPose(a.frames[i].pose,b.frames[i].pose)<1e-5,`${motion} ${sheathe} future leaked at ${i}`);
  assert.equal(a.frames[i].phase,b.frames[i].phase);assert.equal(a.frames[i].progress,b.frames[i].progress);
 }
 assert(a.frames.every(f=>f.pose.every(t=>[...t.p,...t.q].every(Number.isFinite))),'finite poses');
 assert(a.plan.arrives&&a.completionTick,'saved fixture completes');
 assert(a.frames.some(f=>f.phase==='Slide'));
 assert(H.sample(a,1.123).pose.every(t=>t.q.every(Number.isFinite)),'smooth fractional playback');
 const shorter=H.prepare(data,setup,{...options,duration:1});
 for(let i=0;i<shorter.frames.length;i++)assert(maxPose(a.frames[i].pose,shorter.frames[i].pose)<1e-5,'time budget must not influence planning');
 // Same input prefix with a changed future must alter later results, otherwise
 // the test could pass by ignoring gait altogether.
 assert(a.frames.slice(cutoff+1,60).some((f,i)=>maxPose(f.pose,b.frames[cutoff+1+i].pose)>1),'later input is consumed');
 report.push({motion,sheathe,arrival:a.plan.endTick,complete:a.completionTick,solves:a.plan.endpointSolves});
}
for(const sheathe of [true,false]){
 const options={...settings(sheathe),motion:'run'},a=H.prepare(data,setup,options);
 const curved=H.retime(a,{...options,[sheathe?'sheatheCurve':'drawCurve']:[[.2,.03],[.4,.2],[.6,.8],[.8,.97]]});
 assert.notEqual(a.sourceFrames,curved.sourceFrames,'curve edits rerun the causal simulation');
 for(let i=0;i<Math.min(a.frames.length,curved.frames.length);i++)assert.deepEqual(a.frames[i].pose[a.pelvis],curved.frames[i].pose[curved.pelvis],'gait clock remains independent');
 const sequence=Playback.prepare(data,setup,{...options,sequenceMode:true});
 assert(sequence.sequence.second?.online,'both sequence actions use causal planning');
 assert.equal(sequence.sequence.second.motionOffset,sequence.sequence.offset);
 const off=H.retime(a,{...options,noCheat:false});assert(!off.online,'reference planner restored');
}
console.log(JSON.stringify({pass:true,cases:report},null,2));
