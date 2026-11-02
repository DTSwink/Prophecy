'use strict';
// Diagnostic reconstruction, not a claim to restore the original worker VM.
// The capture lacks its previous predicted source and checkpoint. This uses
// the explicit actual-history checkpoint contract with the exact captured
// receipts/future, preserving the real terrain and current pose history.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'Saved/Diagnostics/FootIKPort20261030');
const capture=path.join(dir,'slow-live-request.json'),input=JSON.parse(fs.readFileSync(capture,'utf8'));
if(input.op!=='liveEvaluate'||!input.acceptedFrames?.length)throw Error('Expected captured liveEvaluate with actual history');
const actual=input.acceptedFrames;if(!actual.every((e,i)=>!i||e.tick===actual[i-1].tick+1))throw Error('Captured actual history is not contiguous');
const fine=process.argv.includes('--fine'),availableHistory=process.argv.includes('--available-history'),deployed=path.join(root,'Content/FootIKLab/Runtime.js');
let runtime=deployed;
if(fine){
 let text=fs.readFileSync(deployed,'utf8');
 for(const [module,names] of [['footik.js',['geometry','at','solve','stableLeg','clearanceCurve','reachable','plantedRoll','landingRotation','releaseRotation']],['support.js',['footPoints','footFrame','leg']]]){
  const start=text.indexOf('"'+module+'": function('),end=text.indexOf('\n    "',start+1);if(start<0||end<0)throw Error('Diagnostic module seam changed');let body=text.slice(start,end);
  for(const name of names){const from='function '+name+'(',tag=module+':'+name,to='function '+name+'(...args){return globalThis.__footikFineStage('+JSON.stringify(tag)+',()=>profile_'+name+'(...args));}\nfunction profile_'+name+'(';if(body.split(from).length!==2)throw Error('Diagnostic function seam changed: '+tag);body=body.replace(from,to);}
  text=text.slice(0,start)+body+text.slice(end);
 }
 // Reuse the existing diagnostic shadow rather than retaining another bundle.
 runtime=path.join(dir,'profile-live-native-runtime.js');fs.writeFileSync(runtime,'globalThis.__footikFineStage=(name,fn)=>fn();\n'+text);
}
const script=path.join(dir,'profile-live-captured.js');
fs.writeFileSync(script,`(function(){
const input=JSON.parse(readFile(${JSON.stringify(capture)}));let actual=input.acceptedFrames;
if(${availableHistory}){
 const R=FootIKRequire('recovery.js'),first=Math.ceil(actual[0].tick/4)*4,last=actual.at(-1).tick,source=input.source,sourceStart=input.sourceStartTick,rootStart=input.terrain.rootStartTick||0;
 const rows=[],roots=[],poses=[],angles=[];let lastYaw;
 const appendYaw=y=>{lastYaw=lastYaw===undefined?y:lastYaw+((((y-lastYaw)+180)%360+360)%360-180);angles.push(lastYaw);};
 for(let tick=first;tick<=last;tick+=4){const frame=actual.find(e=>e.tick===tick)?.frame,raw=frame?.raw,h=frame?.rootHeading;if(!raw||!h)throw Error('Missing exact raw row for available-history reconstruction');const y=raw.points[0][1],flat=raw.points.map(p=>[p[0],p[1]-y,p[2]]),axes=raw.axes||raw.q.map(R.toAxes);roots.push(flat[0]);poses.push({points:flat.slice(1),axes:axes.slice(1)});appendYaw(Math.atan2(h[0],h[2])*180/Math.PI);rows.push({time:(tick-first)/120,position:raw.points[0]});}
 const lastRaw=first+(poses.length-1)*4,skip=Math.max(0,(lastRaw+4-sourceStart)/4);
 for(let i=skip;i<source.poses.length;i++){roots.push(source.roots[i]);poses.push(source.poses[i]);appendYaw(source.rootYawDegrees[i]);}
 for(const row of input.terrain.rootRows){const tick=rootStart+row.time*120;if(tick>lastRaw+1e-7)rows.push({...row,time:(tick-first)/120});}
 const duration=(poses.length-1)/30;input.source={...source,roots,poses,rootYawDegrees:angles,duration,totalDuration:duration,directionMeta:{...source.directionMeta,totalDuration:duration}};
 input.sourceStartTick=first;input.terrain={...input.terrain,rootStartTick:first,rootRows:rows};actual=input.acceptedFrames=actual.filter(e=>e.tick>=first);
 delete input.initialHistory;delete input.acceptedHistoryCheckpoint;
}else input.acceptedHistoryCheckpoint={startTick:actual[0].tick,endTick:actual.at(-1).tick};
const captured={epoch:input.epoch,currentTick:input.currentTick,sourceStartTick:input.sourceStartTick,sourceEndTick:input.sourceStartTick+(input.source.poses.length-1)*4,actualStartTick:actual[0].tick,actualEndTick:actual.at(-1).tick,actualCount:actual.length,tiles:input.terrain.tiles.length,sourceRows:input.source.poses.length};
const request=JSON.stringify(input),K=FootIKRequire('footik.js'),Live=FootIKRequire('live-terrain.cjs'),Boundary=FootIKRequire('stair-boundary.cjs'),H=FootIKRequire('handoff.js'),stages={},prepares=[];
const stack=[];function mark(name,fn){const call={at:Date.now(),child:0};stack.push(call);try{return fn();}finally{const duration=Date.now()-call.at;stack.pop();if(stack.length)stack.at(-1).child+=duration;const s=stages[name]||(stages[name]={calls:0,inclusiveWallMs:0,exclusiveWallMs:0});s.calls++;s.inclusiveWallMs+=duration;s.exclusiveWallMs+=duration-call.child;}}
globalThis.__footikFineStage=mark;
function wrap(object,key,name){const original=object[key];object[key]=function(...args){return mark(name,()=>original.apply(this,args));};}
const create=Live.create;Live.create=function(...args){const t=create(...args);for(const key of ['floorFor','reachable','influence','landing'])if(t[key])wrap(t,key,'terrain.'+key);return t;};
wrap(K,'decode','decode');wrap(Boundary,'importFrame','importFrame');wrap(H,'requestFor','handoffRequest');wrap(H,'apply','handoffApply');
const boundary=Boundary.create;Boundary.create=function(...args){return mark('boundaryCreate',()=>{const host=boundary(...args);for(const key of ['contacts','trajectory'])if(host[key])wrap(host,key,'boundary.'+key);return host;});};
const prepare=K.prepare;K.prepare=function(run,settings,host){const cpu=nativeThreadMilliseconds(),wall=Date.now(),floor=nativeFloorCallCount(),reach=typeof nativeReachCallCount==='function'?nativeReachCallCount():0;try{return prepare(run,settings,host);}finally{prepares.push({frames:Math.round(run.duration*120)+1,boundary:!!host.contacts,cpuMs:nativeThreadMilliseconds()-cpu,wallMs:Date.now()-wall,floorCalls:nativeFloorCallCount()-floor,reachCalls:typeof nativeReachCallCount==='function'?nativeReachCallCount()-reach:0});}};
wrap(JSON,'parse','jsonParse');wrap(JSON,'stringify','jsonStringify');
const cpu=nativeThreadMilliseconds(),wall=Date.now(),text=FootIKNative.command(request),cpuMs=nativeThreadMilliseconds()-cpu,wallMs=Date.now()-wall,reply=JSON.parse(text);if(!reply.ready)throw Error('Captured-history reconstruction did not publish: '+text);
const status=reply.diagnostics,feet=reply.frame.feet.map(f=>({state:f.state,surface:f.contact?.surface||null,error:f.error}));
FootIKNative.command(JSON.stringify({op:'close'}));
print(JSON.stringify({passed:true,kind:${JSON.stringify(availableHistory?'available exact captured history plus future; missing acknowledged history is not invented, so this is shorter than the original retained course':'exact captured actual-history checkpoint plus future; original retained predicted source/checkpoint not captured')},captured,inputCharacters:request.length,cpuMs,wallMs,prepares,stages,status,currentFeet:feet}));})();`);
const description={runtime,script,captureSha256:crypto.createHash('sha256').update(fs.readFileSync(capture)).digest('hex'),fineInstrumentation:fine};
if(process.argv.includes('--write-only')){console.log(JSON.stringify(description,null,2));process.exit(0);}
const probe=process.env.FOOTIK_REACH_PROBE||path.join(dir,'math-build/Release/footik_v8_probe.exe');
const result=cp.spawnSync(probe,[runtime,script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.join(root,'Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
if(result.error||result.status!==0)throw result.error||Error(result.stderr||result.stdout);
const report={...JSON.parse(result.stdout),...description};fs.writeFileSync(path.join(dir,fine?'live-captured-fine.json':'live-captured-profile.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
