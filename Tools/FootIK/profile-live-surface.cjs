'use strict';
// Instrument a Saved-only package copy. Timers wrap the actual solver calls,
// excluding JSON transport and oracle comparisons. Canonical sources untouched.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),args=process.argv.slice(2),node=args.includes('--node'),duplicates=args.includes('--duplicates');
const file=key=>path.join(directory,key),runtime=fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8');
const needle='result = liveSurfaceStep(a);';if(runtime.split(needle).length!==2)throw Error('Surface dispatch changed');
const packageFile=file('profile-runtime.js'),probeFile=file('profile-live-surface.js');
let instrumented=runtime.replace(needle,"result = globalThis.__footikMeasure('surface', () => liveSurfaceStep(a));");
if(duplicates){const geometry='function evaluateGeometry(c, v) {';if(instrumented.split(geometry).length!==2)throw Error('Entry geometry hook changed');instrumented=instrumented.replace(geometry,geometry+'globalThis.__footikDuplicate("entry.evaluateGeometry",c,v);');}
fs.writeFileSync(packageFile,instrumented);
fs.writeFileSync(probeFile,`(function(){
const input=JSON.parse(readFile(${JSON.stringify(file('current-yaw-stop10.input.json'))})),capture=JSON.parse(readFile(${JSON.stringify(file('root-support-capture.json'))})),expected=JSON.parse(readFile(${JSON.stringify(file('current-yaw-stop10.expected.json'))}));
const totals={},duplicateTotals={},rows=[],now=()=>performance.now(),cpuNow=typeof nativeThreadMilliseconds==='function'?nativeThreadMilliseconds:()=>0;let tick=-1,duplicateTick=-2,seen=new WeakMap();
globalThis.__footikDuplicate=function(label,owner,args){if(duplicateTick!==tick){seen=new WeakMap();duplicateTick=tick;}let maps=seen.get(owner);if(!maps){maps={};seen.set(owner,maps);}const map=maps[label]||(maps[label]=new Map()),total=duplicateTotals[label]||(duplicateTotals[label]={calls:0,hits:0,evictions:0,capacityPerOwner:512});const key=JSON.stringify(args,(_k,v)=>Object.is(v,-0)?'-zero':v);total.calls++;if(map.has(key)){total.hits++;return;}map.set(key,1);if(map.size>512){map.delete(map.keys().next().value);total.evictions++;}};
globalThis.__footikMeasure=function(key,fn){const cpu=key==='surface'?cpuNow():0,start=now(),result=fn(),elapsed=now()-start,cpuMs=key==='surface'?cpuNow()-cpu:0;const total=totals[key]||(totals[key]={calls:0,ms:0,maxMs:0});total.calls++;total.ms+=elapsed;total.maxMs=Math.max(total.maxMs,elapsed);if(tick>=0){const row=rows[tick]||(rows[tick]={tick});row[key]=(row[key]||0)+elapsed;if(key==='surface')row.cpuMs=cpuMs;}return result;};
const wrap=(object,key,label)=>{const original=object[key];object[key]=function(...args){if(${duplicates}&&key==='feasibleSwivel')__footikDuplicate(label,object,args);if(${duplicates}&&key==='solveArm'){const [p,side,target,pole,handQ]=args,a=object.arms[side==='left'?'l':side==='right'?'r':side];__footikDuplicate(label,object,[side,p.points[a.upper],p.points[a.lower],p.points[a.hand],p.q[input.parents[a.upper]],target,pole,handQ]);}return __footikMeasure(label,()=>original.apply(this,args));};};
for(const [moduleName,factory,methods] of [['slide-arms.js','create',['step','clear','contact']],['slide-entry.js','create',['sample']],['slide-joints.js','build',['solveArm','feasibleSwivel']]]){
 const module=FootIKRequire(moduleName),original=module[factory];module[factory]=function(...args){const object=__footikMeasure(moduleName+':'+factory,()=>original.apply(this,args));for(const key of methods)wrap(object,key,moduleName+':'+key);return object;};
}
globalThis.__footikNN=()=>{throw Error('External-root diagnostic may not call NN');};
const command=value=>JSON.parse(FootIKNative.command(JSON.stringify(value))),p=capture.parameters,extent=Math.max(28,p.speed*p.duration+.5*Math.abs(p.gravity)*p.duration**2+2*p.height);
command({op:'liveSurfaceInit',source:input.source,parents:input.parents,settings:p.s,height:p.height,speed:p.speed,canonicalTerrain:true,extent,rootFrames:capture.records.map(r=>r.context)});
const same=(a,b,label)=>{if(b===null||typeof b!=='object'){if(a!==b)throw Error(label+' changed');return;}if(Array.isArray(b)&&a.length!==b.length)throw Error(label+' length');for(const k of Object.keys(b))same(a[k],b[k],label+'.'+k);};
for(tick=0;tick<expected.frames.length;tick++){
 const result=command({op:'liveSurfaceStep',currentTick:tick,commands:[capture.commands[tick]],rootReceipt:capture.records[tick].receipt});
 for(const key of ['root','feet','surface','slide','pelvisOffset','influence'])same(result.frame[key],expected.frames[tick][key],'frame'+tick+'.'+key);
 same(result.frame.pose.points,expected.frames[tick].pose.points,'points'+tick);same(result.frame.pose.q,expected.frames[tick].pose.q,'q'+tick);
 same(result.supports,capture.records[tick].supports,'supports'+tick);
 rows[tick].slide=!!capture.records[tick].context.slide;
}
command({op:'liveSurfaceClose'});
const slideStart=capture.records.findIndex(r=>r.context.slide),warmStart=slideStart+Math.ceil(Math.max(p.s.slideBlend,p.s.slideLegBlend,p.s.slidePelvisBlend)*120);
const summarize=selection=>{const values=selection.map(r=>r.surface||0).sort((a,b)=>a-b),cpu=selection.reduce((s,r)=>s+(r.cpuMs||0),0);return {ticks:values.length,totalMs:values.reduce((a,b)=>a+b,0),meanMs:values.reduce((a,b)=>a+b,0)/values.length,p50Ms:values[Math.floor(values.length*.5)],p95Ms:values[Math.floor(values.length*.95)],maxMs:values[values.length-1],threadCpuTotalMs:cpu,threadCpuMeanMs:cpu/values.length};};
print(JSON.stringify({passed:true,allFramesExact:true,transportExcluded:true,clockResolution:${JSON.stringify(node?'performance.now':'Date.now wall + GetThreadTimes CPU, aggregate CPU recommended')},slideStart,warmStart,total:summarize(rows),warm:summarize(rows.filter(r=>r.tick>=warmStart)),totals,duplicateTotals,rows}));
})();`);
const env={...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.resolve(__dirname,'../../Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')};
const nodeLoader="const fs=require('fs'),vm=require('vm');global.readFile=p=>fs.readFileSync(p,'utf8');global.print=console.log;for(const p of process.argv.slice(1))vm.runInThisContext(fs.readFileSync(p,'utf8'),{filename:p});";
const probe=file('math-build/Release/footik_v8_probe.exe'),run=cp.spawnSync(node?process.execPath:probe,node?['-e',nodeLoader,packageFile,probeFile]:[packageFile,probeFile],{encoding:'utf8',windowsHide:true,env,maxBuffer:4*1024*1024,timeout:180000});
if(run.error||run.status!==0)throw run.error||Error(run.stderr||run.stdout);
const result=JSON.parse(run.stdout),metrics=run.stderr.match(/PROBE_METRICS (\{[^\n]+\})/);if(metrics)result.process=JSON.parse(metrics[1]);
fs.writeFileSync(file('profile-live-surface-'+(node?'node':'native')+(duplicates?'-duplicates':'')+(args.find(a=>a.startsWith('--label='))?'-'+args.find(a=>a.startsWith('--label=')).slice(8):'')+'.json'),JSON.stringify(result,null,2));delete result.rows;console.log(JSON.stringify(result,null,2));
