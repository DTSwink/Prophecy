'use strict';
// Offline session parity. Replays captured policy replies: no server, worker,
// fresh inference, UI, saved-state write, or background process.
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),readline=require('node:readline');
const K=require('./footik.js'),C=require('./surface-coupling.js'),rig=require('./data/rig.json');
let checks=0;
const check=(x,message)=>{checks++;assert.ok(x,message);};
(async()=>{
 const reports=[];
 // New captured fixtures may be supplied after root/trigger behavior changes;
 // old policy replies cannot be replayed past a different inference schedule.
 const fixtures=process.argv.slice(2);
 const inputs=fixtures.length?fixtures:[2,5].map(threshold=>path.join(__dirname,'snapshots',`slide-live-${threshold}.json.gz`));
 for(const [fixtureIndex,fixturePath] of inputs.entries()){
  const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(fixturePath))),threshold=request.settings.slideSpeed;
  const run=K.decode(request.source,rig.parents),requests=[];
  const whole=await C.compute(run,request.settings,async(r,i)=>{requests.push(JSON.stringify(r));return response.steps[i];});
  const calls=[],session=C.createSession(run,request.settings,async(r,i)=>{calls.push(JSON.stringify(r));return response.steps[i];}),frames=session.model.frames;
  const references=[],bytes=[];
  for(const end of [0,1/30,.05,.3,.36666666666666664,.5,.8,1.82,2.1,3.25,5]){
   const before=session.model.frames.length,result=await session.extend(end),tick=Math.ceil(end*120-1e-8);
   check(result.model===session.model&&result.model.frames===frames,'Retain model/frames identity');
   check(frames.length===tick+1,'Generate exactly the requested120Hz prefix');
   check(Math.abs(session.generatedThrough-tick/120)<1e-10,'Correct generatedThrough');
   for(let i=0;i<before;i++){check(frames[i]===references[i],'Retain every previous frame object');check(JSON.stringify(frames[i])===bytes[i],'Never mutate completed frame data');}
   for(let i=before;i<frames.length;i++){references[i]=frames[i];bytes[i]=JSON.stringify(frames[i]);check(bytes[i]===JSON.stringify(whole.model.frames[i]),'Split extension matches one-pass frame');}
   const n=calls.length;await session.extend(Math.max(0,end-.1));check(calls.length===n&&frames.length===tick+1,'Shrinking performs no extra work');
   if(end===1/30)check(calls.length===0,'Exact boundary does not infer its unused next pose');
  }
  assert.deepEqual(calls,requests);checks++;
  assert.deepEqual(session.model.metrics,whole.model.metrics);checks++;
  // Metadata calibrates the root once. A three-frame source is enough to
  // start the coupled policy; no late source pose is sampled for previews.
  const height=run.referenceHeight??run.directionMeta?.referenceHeight??Array.from({length:601},(_,i)=>K.at(run,i/120)).reduce((sum,p)=>sum+p.points[1][1]-p.points[0][1],0)/601;
  const seed=K.decode({...request.source,duration:.1,poses:request.source.poses.slice(0,4),roots:request.source.roots.slice(0,4),directionMeta:{...request.source.directionMeta,totalDuration:5,referenceHeight:height}},rig.parents);
  const originalAt=K.at;let maxSourceTime=0;
  K.at=(source,time)=>{if(source===seed){maxSourceTime=Math.max(maxSourceTime,time);check(time<=1/30+1e-9,'No future seed-pose sampling');}return originalAt(source,time);};
  let bounded;
  try{bounded=C.createSession(seed,request.settings,async(_,i)=>response.steps[i]);await bounded.extend(.8);const prefix=bounded.model.frames.slice();await bounded.extend(5);check(prefix.every((f,i)=>bounded.model.frames[i]===f),'Bounded seed extension retains frame prefix');}
  finally{K.at=originalAt;}
  check(bounded.model.duration===5&&bounded.model.frames.length===601,'Seed length does not shorten timeline');
  // Calibration speed can differ by tiny float serialization error, so compare
  // actual root positions numerically while retaining byte-exact split checks above.
  let rootError=0;for(let i=0;i<601;i++)rootError=Math.max(rootError,...bounded.model.frames[i].root.map((v,k)=>Math.abs(v-whole.model.frames[i].root[k])));
  check(rootError<1e-5,'Bounded source retains calibrated root motion');
  // Cancellation pauses at the committed checkpoint; retry preserves it.
  let cancelled=false,policyCalls=0;
  const pause=C.createSession(seed,request.settings,async(_,i)=>{policyCalls++;if(i===1)cancelled=true;return response.steps[i];});
  check(await pause.extend(.3,()=>cancelled)===null,'Cancelled extension does not publish success');
  const savedPrefix=pause.model.frames.slice(),last=pause.generatedThrough;cancelled=false;await pause.extend(.3);
  check(savedPrefix.every((f,i)=>pause.model.frames[i]===f)&&pause.generatedThrough>last,'Cancellation resume keeps prefix');
  check(policyCalls===pause.steps.length,'Cancellation never re-infers a policy prefix');
  if(fixtureIndex===0){
   // Browser preparation consumes cumulative wire replies and extends only
   // missing frames. Replace network with this captured offline service.
   const oldHTTP=globalThis.FootHTTP;globalThis.FootHTTP={request:async name=>{const b=fs.readFileSync(path.join(__dirname,name));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);}};
   let networkCalls=0;const peer=C.createSession(seed,request.settings,async(_,i)=>response.steps[i]);
   const batches=[];let solveCalls=0,serverSolveCalls=0;const savedSolve=K.solve;K.solve=(...args)=>{solveCalls++;return savedSolve(...args);};
   const preparation=C.createPreparation(seed,request.settings,async(_,req)=>{
    networkCalls++;const start=peer.model.frames.length;await peer.extend(req.endTime);serverSolveCalls=solveCalls;
    const frames=peer.model.frames.slice(start);batches.push({start,count:frames.length,data:z.gzipSync(JSON.stringify(frames),{level:1}).toString('base64')});
    return {kind:'surface',sessionId:'offline-session',steps:peer.steps,generatedThrough:peer.generatedThrough,frameEncoding:'gzip-json-v1',frameBatches:batches,diagnostics:{metrics:peer.model.metrics,events:peer.model.events,coupling:peer.model.coupling}};
   });
   try{const short=await preparation.extend(.05),prefix=short.frames.slice();await preparation.extend(.3);const count=networkCalls;await preparation.extend(.05);check(networkCalls===count,'Preparation shrink has no network or tail request');check(prefix.every((f,i)=>preparation.model.frames[i]===f),'Preparation retains published frame objects');check(preparation.generatedThrough===.3,'Preparation reports generated extent');await preparation.extend(1.2);check(solveCalls===serverSolveCalls,'Viewer never repeats a server IK solve');check(JSON.stringify(preparation.model.frames)===JSON.stringify(peer.model.frames),'Compressed poses retain every solved value through slide');}
   finally{globalThis.FootHTTP=oldHTTP;K.solve=savedSolve;}
   // One owned short-lived Node peer verifies the persistent protocol and
   // ordinary EOF cleanup; it replays one captured reply and runs no NN.
   const child=spawn(process.execPath,[path.join(__dirname,'surface_driver.cjs')],{cwd:__dirname,stdio:['pipe','pipe','pipe'],windowsHide:true});
   const lines=readline.createInterface({input:child.stdout,crlfDelay:Infinity})[Symbol.asyncIterator]();
   const exit=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',code=>resolve(code));});
   const send=value=>child.stdin.write(JSON.stringify(value)+'\n');
   const next=async()=>JSON.parse((await lines.next()).value);
   try{
    send({source:C.sourceData(seed),settings:request.settings,endTime:1/30,totalDuration:5});
    const one=await next();check(one.done&&one.steps.length===0&&one.generatedThrough===1/30,'Driver stops before unused boundary inference');
    check(one.frameBatch.start===0&&one.frameBatch.count===5&&(await C.decodeFrameBatch(one.frameBatch)).length===5,'Driver sends lossless bounded pose prefix');
    send({extend:.05});const needed=await next();check(!!needed.step,'Driver requests only next tail policy step');send(response.steps[0]);
    const two=await next();check(two.done&&two.stepStart===0&&two.steps.length===1&&two.generatedThrough===.05,'Driver emits delta steps and exact extent');
    check(two.frameBatch.start===5&&two.frameBatch.count===2,'Driver emits only appended poses');
    send({extend:0});const shrink=await next();check(shrink.done&&shrink.stepStart===1&&shrink.steps.length===0&&shrink.generatedThrough===.05,'Driver shrink does not regenerate');
    child.stdin.end();const timeout=new Promise((_,reject)=>{const t=setTimeout(()=>reject(Error('Idle surface peer did not exit on EOF')),2500);t.unref();});check(await Promise.race([exit,timeout])===0,'Idle peer exits normally on EOF');
   }finally{if(child.exitCode===null)child.kill();}
  }
  reports.push({fixture:path.basename(fixturePath),threshold,frames:frames.length,nnSteps:calls.length,maxSourceTime,rootError});
 }
 console.log(JSON.stringify({checks,reports}));
})().catch(error=>{console.error(error);process.exitCode=1;});
