'use strict';
// Diagnostic only: the deployed runtime is read, never changed. Uses the
// existing bounded delayed-history fixture, not a captured Unreal request.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'Saved/Diagnostics/FootIKPort20261030');
const script=path.join(dir,'profile-live-native-planning.js');
const input=path.join(dir,'walk-stairs.input.json');
const fine=process.argv.includes('--fine');
const cache=Number(process.argv.find(a=>a.startsWith('--cache='))?.split('=')[1]||0);
if(![0,1,8,64].includes(cache))throw Error('Cache probe capacity must be0,1,8or64');
let runtime=path.join(root,'Content/FootIKLab/Runtime.js');
if(fine||cache){
 let text=fs.readFileSync(runtime,'utf8');
 for(const [module,names] of fine?[['footik.js',['geometry','at','solve','stableLeg','clearanceCurve','reachable','plantedRoll','landingRotation','releaseRotation']],['support.js',['footPoints','footFrame','leg']]]:[]){
  const start=text.indexOf('"'+module+'": function('),end=text.indexOf('\n    "',start+1);if(start<0||end<0)throw Error('Diagnostic module seam changed');let body=text.slice(start,end);
  for(const name of names){const from='function '+name+'(',tag=module+':'+name,to='function '+name+'(...args){return globalThis.__footikFineStage('+JSON.stringify(tag)+',()=>profile_'+name+'(...args));}\nfunction profile_'+name+'(';if(body.split(from).length!==2)throw Error('Diagnostic function seam changed: '+tag);body=body.replace(from,to);}
  text=text.slice(0,start)+body+text.slice(end);
 }
 if(cache){
  const start=text.indexOf('"native-terrain-floor.cjs": function('),end=text.indexOf('\n    "',start+1);let body=text.slice(start,end);
  const from='return solve(input, output) && Number.isFinite(output[0]) ? output[0] : null;';if(body.split(from).length!==2)throw Error('Native floor diagnostic seam changed');
  body=body.replace('const output = new Float64Array(1);','const output = new Float64Array(1), cache=[];let replace=0;');
  body=body.replace(from,`const stats=globalThis.__footikFloorCacheStats||(globalThis.__footikFloorCacheStats={queries:0,hits:0,misses:0});stats.queries++;
for(const entry of cache){const data=entry.data;if(data.length!==3+3*count||!Object.is(data[0],input[2])||!Object.is(data[1],input[3])||!Object.is(data[2],input[4]))continue;let equal=true;for(let i=3;i<data.length;i++)if(!Object.is(data[i],input[prefix.length+i-3])){equal=false;break;}if(equal){stats.hits++;return entry.value;}}
stats.misses++;const result=solve(input,output)&&Number.isFinite(output[0])?output[0]:null;if(result===null)return result;
let entry=cache[replace];if(!entry){entry={data:new Float64Array(3+3*count),value:result};cache.push(entry);}else if(entry.data.length!==3+3*count)entry.data=new Float64Array(3+3*count);
entry.data[0]=input[2];entry.data[1]=input[3];entry.data[2]=input[4];for(let i=3;i<entry.data.length;i++)entry.data[i]=input[prefix.length+i-3];entry.value=result;replace=(replace+1)%${cache};return result;`);
  text=text.slice(0,start)+body+text.slice(end);
 }
 runtime=path.join(dir,'profile-live-native-runtime.js');fs.writeFileSync(runtime,'globalThis.__footikFineStage=(name,fn)=>fn();\n'+text);
}
const code=String.raw`(function(){
const input=JSON.parse(readFile(INPUT_PATH)),K=FootIKRequire('footik.js'),T=FootIKRequire('terrain.js'),R=FootIKRequire('recovery.js'),B=FootIKRequire('stair-boundary.cjs'),P=FootIKRequire('live-stair-planner.cjs'),H=FootIKRequire('handoff.js');
const run=K.decode(input.source,input.parents),standard=T.create(input.settings),stages={},prepares=[],commands=[];
function frame(tick){const p=K.at(run,tick/120),height=standard.rootHeight(p.points[0][2]),pose={...p,points:p.points.map(v=>[v[0],v[1]+height,v[2]])};return {pose,raw:pose,root:pose.points[0],rootHeading:[0,0,1],pelvisOffset:0,influence:0,feet:[20,24].map((j,i)=>({side:i?'R':'L',state:'NN',target:pose.points[j],contact:null,error:0,penetration:0}))};}
function window(from,to){const source={...input.source,roots:input.source.roots.slice(from/4,to/4+1),poses:input.source.poses.slice(from/4,to/4+1),rootYawDegrees:Array.from({length:(to-from)/4+1},()=>0),duration:(to-from)/120,totalDuration:(to-from)/120};source.directionMeta={...source.directionMeta,totalDuration:source.duration};return {source,sourceStartTick:from,terrain:{rootStartTick:from,rootRows:source.roots.map((p,i)=>({time:i/30,position:[p[0],standard.rootHeight(p[2]),p[2]]})),tiles:standard.tiles.map(t=>({id:t.id,point:[0,t.y,0],u:[1,0,0],v:[0,0,1],bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')}))}};}
const first={...input,op:'liveEvaluate',epoch:'diagnostic',...window(0,48),origin:[0,0,0],currentTick:0},later={op:'liveEvaluate',epoch:'diagnostic',parents:input.parents,settings:input.settings,...window(184,336),origin:[0,0,0],currentTick:188,acceptedFrames:Array.from({length:189},(_,tick)=>({tick,frame:frame(tick)}))};
const inputs=[JSON.stringify(first),JSON.stringify(later)];
function mark(name,fn){const t=Date.now();try{return fn();}finally{const s=stages[name]||(stages[name]={calls:0,wallMs:0});s.calls++;s.wallMs+=Date.now()-t;}}
globalThis.__footikFineStage=mark;
function wrap(object,key,name){const original=object[key];object[key]=function(...args){return mark(name,()=>original.apply(this,args));};}
const Live=FootIKRequire('live-terrain.cjs'),createTerrain=Live.create;Live.create=function(...args){const t=createTerrain(...args);wrap(t,'floorFor','terrain.floorFor');wrap(t,'influence','terrain.influence');wrap(t,'landing','terrain.landing');return t;};
wrap(K,'decode','decode');wrap(B,'importFrame','importFrame');wrap(H,'requestFor','handoffRequest');wrap(H,'apply','handoffApply');wrap(T,'create','terrainCreate');
const makeBoundary=B.create;B.create=function(...args){return mark('boundaryCreate',()=>{const b=makeBoundary(...args);for(const key of ['contacts','trajectory'])if(b[key])wrap(b,key,'boundary.'+key);return b;});};
const prepare=K.prepare;K.prepare=function(source,settings,host){const cpu=nativeThreadMilliseconds(),wall=Date.now(),calls=nativeFloorCallCount();try{return prepare(source,settings,host);}finally{prepares.push({frames:Math.round(source.duration*120)+1,boundary:!!host.contacts,cpuMs:nativeThreadMilliseconds()-cpu,wallMs:Date.now()-wall,nativeFloorCalls:nativeFloorCallCount()-calls});}};
const create=P.create;P.create=function(...args){const p=create(...args);wrap(p,'plan','plan');return p;};
wrap(JSON,'parse','jsonParse');wrap(JSON,'stringify','jsonStringify');
for(let i=0;i<inputs.length;i++){const before=Object.fromEntries(Object.entries(stages).map(([k,v])=>[k,{...v}])),at=prepares.length,cpu=nativeThreadMilliseconds(),wall=Date.now(),reply=FootIKNative.command(inputs[i]),cost={cpuMs:nativeThreadMilliseconds()-cpu,wallMs:Date.now()-wall};const parsed=JSON.parse(reply);if(!parsed.ready)throw Error('Profile failed to publish');commands.push({name:i?'delayedActual':'initial',inputCharacters:inputs[i].length,...cost,status:parsed.diagnostics,prepares:prepares.slice(at),stages:Object.fromEntries(Object.entries(stages).map(([k,v])=>[k,{calls:v.calls-(before[k]?.calls||0),wallMs:v.wallMs-(before[k]?.wallMs||0)}]))});}
FootIKNative.command(JSON.stringify({op:'close'}));print(JSON.stringify({passed:true,source:'Saved synthetic delayed actual history; actual Unreal worker payload was not captured',inferenceEnabled:false,commands,floorCache:globalThis.__footikFloorCacheStats}));
})();`.replace('INPUT_PATH',JSON.stringify(input));
fs.writeFileSync(script,code);
if(process.argv.includes('--write-only')){console.log(JSON.stringify({runtime,script,fine,cache}));process.exit(0);}
const result=cp.spawnSync(path.join(dir,'math-build/Release/footik_v8_probe.exe'),[runtime,script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.join(root,'Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
if(result.error||result.status!==0)throw result.error||Error(result.stderr||result.stdout);
const report=JSON.parse(result.stdout);report.fineInstrumentation=fine;report.cacheCapacity=cache;fs.writeFileSync(path.join(dir,cache?'live-native-planning-cache'+cache+'.json':fine?'live-native-planning-fine.json':'live-native-planning-profile.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
