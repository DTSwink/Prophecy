'use strict';
// Replay a recorded policy prefix: no NN process, server edits or live state writes.
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const folder=path.resolve(__dirname,'../../Saved/FootIKPerf20261029');
const record=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(folder,'current-session.gz'))));
const K=require('./footik.js'),C=require('./surface-coupling.js');
const run=K.decode(record.request.source,require('./data/rig.json').parents);
run.totalDuration=record.request.totalDuration;
const input=record.request.settings,end=record.generatedThrough;
(async()=>{
 const start=performance.now(),session=C.createSession(run,input,async(_,i)=>{assert(record.steps[i],'Unexpected policy step '+i);return record.steps[i];});
 const {model}=await session.extend(end),ms=performance.now()-start;
 const frames=JSON.stringify(model.frames),out={ms,frames:model.frames.length,policySteps:session.steps.length,settings:input};
 const name=process.argv[2]||'candidate';
 fs.writeFileSync(path.join(folder,name+'.json'),JSON.stringify(out,null,2));
 fs.writeFileSync(path.join(folder,name+'-frames.json'),frames);
 console.log(JSON.stringify({name,ms,frames:model.frames.length,policySteps:session.steps.length}));
})().catch(e=>{console.error(e);process.exitCode=1;});
