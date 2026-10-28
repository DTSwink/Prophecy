// Short-lived physics peer owned by the single CPU NN worker. No server/UI/state.
const readline=require('readline'),K=require('./footik.js'),C=require('./surface-coupling.js');
const lines=readline.createInterface({input:process.stdin,crlfDelay:Infinity})[Symbol.asyncIterator]();
const send=value=>process.stdout.write(JSON.stringify(value)+'\n');
(async()=>{
 const request=JSON.parse((await lines.next()).value),parents=require('./data/rig.json').parents;
 const run=K.decode(request.source,parents),result=await C.compute(run,request.settings,async step=>{
  send({step});const line=await lines.next();if(line.done)throw Error('NN peer closed');const response=JSON.parse(line.value);if(response.error)throw Error(response.error);return response;
 });
 send({done:true,steps:result.steps,diagnostics:{metrics:result.model.metrics,coupling:result.model.coupling}});
 process.stdin.destroy();
})().catch(error=>{send({error:String(error.stack||error)});process.exitCode=1;process.stdin.destroy();});
