// Bounded/resumable physics peer owned by the CPU NN worker. No server/UI/state.
const readline=require('readline'),zlib=require('zlib'),K=require('./footik.js'),C=require('./surface-coupling.js');
const lines=readline.createInterface({input:process.stdin,crlfDelay:Infinity})[Symbol.asyncIterator]();
const send=value=>process.stdout.write(JSON.stringify(value)+'\n');
(async()=>{
 const first=await lines.next();if(first.done)return;
 const request=JSON.parse(first.value),parents=require('./data/rig.json').parents;let session;
 const reset=request=>{
  session?.close();const run=K.decode(request.source,parents);run.totalDuration=request.totalDuration??request.source.totalDuration??run.directionMeta?.totalDuration??run.duration;
  run.referenceHeight=request.source.referenceHeight??run.directionMeta?.referenceHeight;
  session=C.createSession(run,request.settings,async step=>{
   send({step});const line=await lines.next();if(line.done)throw Error('NN peer closed');const response=JSON.parse(line.value);if(response.error)throw Error(response.error);return response;
  });
 };reset(request);
 const extend=async end=>{
  const stepStart=session.steps.length,frameStart=session.model.frames.length,result=await session.extend(end),frames=result.model.frames.slice(frameStart);
  // Send the solved poses once. Gzip level1 keeps IPC/JSON parsing small without
  // throwing away double precision or doing the solver again in the browser.
  const frameBatch={start:frameStart,count:frames.length,data:zlib.gzipSync(JSON.stringify(frames),{level:1}).toString('base64')};
  send({done:true,stepStart,steps:result.steps.slice(stepStart),frameBatch,generatedThrough:result.model.generatedThrough,diagnostics:{metrics:result.model.metrics,coupling:result.model.coupling,events:result.model.events}});
 };
 const persistent=Number.isFinite(request.endTime);
 await extend(persistent?request.endTime:session.model.duration);
 if(persistent)while(true){
  const line=await lines.next();if(line.done)break;
  const command=JSON.parse(line.value);
  if(command.reset){reset(command.reset);await extend(command.reset.endTime);continue;}
  if(!Number.isFinite(command.extend))throw Error('Expected surface extension end');
  await extend(command.extend);
 }
 session.close();
 process.stdin.destroy();
})().catch(error=>{send({error:String(error.stack||error)});process.exitCode=1;process.stdin.destroy();});
