// Read-only numerical evidence for the legacy stair planner's noncausal span
// dependencies. Run: node Labs/FootIKLab/verify-trim-planner-boundary.cjs
// This does not require inference, a server or UI, and does not change motion.
// The report deliberately does NOT assert that a large difference must remain:
// a future causal planner should improve it. It records why truncating the old
// planner then blindly appending a longer plan is not a safe tail-only change.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const dir=__dirname,sha=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,p))).digest('hex');
const distance=(a,b)=>R.length(R.sub(a,b));
const cases=[];
for(const gait of ['walk','run']){
 const run=load(gait,.21),settings={gait,phase:.21,terrain:'stairs',clearance:1,height:16,depth:35,steps:12};
 const full=K.prepare(run,settings),joints=['pelvis','foot_l','foot_r'].map(name=>({name,index:run.names.indexOf(name)}));
 for(const endTime of [1,1.5]){
  const short=K.prepare({...run,duration:endTime},settings),last=short.frames.length-1;
  let maxPrefixDifference=0,worst=null,maxBoundaryDifference=0,maxBlindSpliceStep=0,maxAcceptedNextStep=0;
  for(let i=0;i<short.frames.length;i++)for(const {name,index}of joints){
   const difference=distance(short.frames[i].pose.points[index],full.frames[i].pose.points[index]);
   if(!Number.isFinite(difference))throw Error('Non-finite comparison');
   if(difference>maxPrefixDifference){maxPrefixDifference=difference;worst={frame60:i/2,joint:name};}
   if(i===last){
    maxBoundaryDifference=Math.max(maxBoundaryDifference,difference);
    maxBlindSpliceStep=Math.max(maxBlindSpliceStep,distance(short.frames[i].pose.points[index],full.frames[i+1].pose.points[index]));
    maxAcceptedNextStep=Math.max(maxAcceptedNextStep,distance(full.frames[i].pose.points[index],full.frames[i+1].pose.points[index]));
   }
  }
  cases.push({gait,settings,shortEndTime:endTime,extendedEndTime:run.duration,sampleHz:short.fps,
   maxPrefixDifferenceMeters:maxPrefixDifference,worst,maxBoundaryDifferenceMeters:maxBoundaryDifference,
   blindSpliceStepMeters:maxBlindSpliceStep,acceptedNextStepMeters:maxAcceptedNextStep,
   shortBoundaryStates:short.frames[last].feet.map(f=>f.state),fullBoundaryStates:full.frames[last].feet.map(f=>f.state)});
 }
}
const result={scope:'Offline stair planner extent sensitivity, using the same fixed cached NN input. No runtime change; surface sessions are separate.',
 coreSha256:sha('footik.js'),bankSha256:{walk:sha('data/walk-phases.bin'),run:sha('data/run-phases.bin')},cases,
 consequence:'Full-span contact fitting, swing endpoints, knee/pelvis lookahead and minimum-curvature fitting can revise the prefix when duration changes. A blind prefix/tail splice is unsafe; preserving the existing stair motion requires its existing lookahead until a causal boundary-state planner is implemented.'};
fs.writeFileSync(path.join(dir,'trim-planner-boundary-verification.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
