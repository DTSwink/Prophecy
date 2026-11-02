'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),read=p=>fs.readFileSync(path.join(root,p),'utf8'),dir=path.join(root,'Saved/Diagnostics/FootIKPort20261030/reach-native'),floorDir=path.join(dir,'../floor-native');
fs.mkdirSync(dir,{recursive:true});
// Test-only switch selects the exact cached-JS baseline in the same warmed VM.
const helper=read('Tools/FootIK/native-terrain-floor.cjs').replace('floor.reachable=function(target,hip,reach,offsets){','floor.reachable=function(target,hip,reach,offsets){\n if(globalThis.DisableNativeReach)return null;');
const live=read('Tools/FootIK/live-terrain.cjs');
let runtime=read('Content/FootIKLab/Runtime.js');
function replaceFactory(name,body){const begin=runtime.indexOf('"'+name+'": function('),end=runtime.indexOf('\n    "',begin+1);if(begin<0||end<0)throw Error('Missing factory '+name);runtime=runtime.slice(0,begin)+'"'+name+'": function(module,exports,require2){\nconst require=name=>require2(name.split("/").pop());\n'+body+'\n    },'+runtime.slice(end);}
replaceFactory('native-terrain-floor.cjs',helper);replaceFactory('live-terrain.cjs',live);
const seam='function reachable(target, hip, reach, offsets, terrain) {';if(!runtime.includes(seam))throw Error('Missing reachable seam');if(!/function reachable\(target, hip, reach, offsets, terrain\) \{\s*if\s*\(terrain\.reachable\)/.test(runtime))runtime=runtime.replace(seam,seam+'\nif(terrain.reachable){const native=terrain.reachable(target,hip,reach,offsets);if(native)return native;}');
const candidate=path.join(dir,'Runtime.reach.js');fs.writeFileSync(candidate,runtime);
const setup=path.join(dir,'setup.js');fs.writeFileSync(setup,`globalThis.OracleFloorLive=(function(){const module={exports:{}},require=name=>FootIKRequire(name.split('/').pop());${fs.readFileSync(path.join(floorDir,'oracle-live-terrain.cjs'),'utf8')}\nreturn module.exports;})();`);
const cases=[['walk-stairs',0],['walk-stairs',37],['run-stairs',90],['walk-down',-135],['run-down',37],['walk-flat',90]].map(([name,angle])=>({id:name+'-'+angle,angle,input:path.join(floorDir,name+'-'+angle+'.input.json'),expected:path.join(floorDir,name+'-'+angle+'.expected.json')}));
const script=path.join(dir,'check.js');fs.writeFileSync(script,`(function(){
const Live=FootIKRequire('live-terrain.cjs'),R=FootIKRequire('recovery.js'),{add,sub,mul,length,unit}=R;
const serial=x=>JSON.stringify(x,(k,v)=>Object.is(v,-0)?'__negative_zero__':v);
function old(target,hip,reach,offsets,terrain){let p=target.slice();for(let pass=0;pass<12;pass++){const d=sub(p,hip);if(length(d)>reach)p=add(hip,mul(unit(d),reach));p[1]=Math.max(p[1],terrain.floorFor(p,offsets));const dy=p[1]-hip[1],horizontal=Math.hypot(p[0]-hip[0],p[2]-hip[2]);const radius=Math.sqrt(Math.max(0,reach*reach-dy*dy));if(horizontal>radius){p[0]=hip[0]+(p[0]-hip[0])*radius/horizontal;p[2]=hip[2]+(p[2]-hip[2])*radius/horizontal;}}return p;}
let seed=72491;const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
const shoe=[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>[x*.06,y*.04,z*.16])));
let checks=0,rejected=0;
for(const angle of [0,37,90,-135]){
 const q=R.qexp([0,angle*Math.PI/180,0]),turn=p=>R.rotate(q,p),snapshot={tiles:[0,1,2].map(i=>({id:'tile'+i,point:turn([0,i*.16,0]),u:turn([1,0,0]),v:turn([0,0,1]),bounds:[-.5,.5,i*.35,(i+1)*.35],shaped:true}))};
 const terrain=Live.create(snapshot),oracle=OracleFloorLive.create(snapshot);
 for(let i=0;i<400;i++){
  const target=turn([(random()-.5)*1.5,random()*1.5,random()*1.5]),hip=turn([(random()-.5)*.5,.4+random(),random()*1.5]),reach=i%31?random()*1.1:0,offsets=shoe.map(turn);
  if(i%9===0)offsets[0][1]+=.001;if(i%17===0)offsets[0][0]=-0;if(i%43===0)target[0]=-0;
  const actual=terrain.reachable(target,hip,reach,offsets),expected=old(target,hip,reach,offsets,oracle);
  if(!actual||actual.some((v,j)=>!Object.is(v,expected[j])))throw Error('Reach difference '+checks+' '+serial({target,hip,reach,actual,expected}));checks++;
 }
}
const empty=Live.create({tiles:[]});for(const z of [-0,0])for(const reach of [0,1,1e-200,1e150]){const t=[0,z,0],hip=[0,z,0],expected=old(t,hip,reach,[],empty),actual=empty.reachable(t,hip,reach,[]);if(actual.some((v,j)=>!Object.is(v,expected[j])))throw Error('Signed zero differs');checks++;}
const raw=new Float64Array([0,0,0,0,0,0,1,0,1]);
for(const variant of [[],[0,0],Array.from(raw).slice(0,-1),[...raw,0],Array.from(raw,(v,i)=>i===0?257:v),Array.from(raw,(v,i)=>i===1?7:v),Array.from(raw,(v,i)=>i===2?NaN:v),Array.from(raw,(v,i)=>i===5?Infinity:v),Array.from(raw,(v,i)=>i===8?-1:v)]){
 const output=new Float64Array([19,-0,23]);if(__footikTerrainReach(new Float64Array(variant),output)||!Object.is(output[1],-0)||output[0]!==19||output[2]!==23)throw Error('Invalid input published');rejected++;
}
for(const size of [0,1,2,4]){const output=new Float64Array(size).fill(19);if(__footikTerrainReach(raw,output)||output.some(x=>x!==19))throw Error('Wrong output size published');rejected++;}
const alias=raw.slice(),expectedAlias=new Float64Array(3);if(!__footikTerrainReach(raw,expectedAlias)||!__footikTerrainReach(alias,alias.subarray(2,5))||expectedAlias.some((v,i)=>!Object.is(v,alias[2+i])))throw Error('Aliased output differs');checks++;
const viewBuffer=new Float64Array(20);viewBuffer.set(raw,4);const viewOut=viewBuffer.subarray(14,17);if(!__footikTerrainReach(viewBuffer.subarray(4,13),viewOut)||viewOut.some((v,i)=>!Object.is(v,expectedAlias[i])))throw Error('Offset view differs');checks++;
const rows=[],cases=${JSON.stringify(cases)};let frames=0,checkpoints=0,pinned=0;
for(const c of ${process.argv.includes('--edges-only')?'[]':'cases'}){const input=JSON.parse(readFile(c.input)),start=nativeThreadMilliseconds(),floor=nativeFloorCallCount(),reach=nativeReachCallCount(),model=FootIKFloorCourse.run(input,c.angle);if(serial(model)!==readFile(c.expected))throw Error(c.id+' complete pose/checkpoint difference');const n=model.frames.length+(model.seeded?.frames.length||0);frames+=n;checkpoints+=1+(model.seeded?1:0);pinned+=model.seeded?.materialPins||0;rows.push({id:c.id,cpuMs:nativeThreadMilliseconds()-start,floorCalls:nativeFloorCallCount()-floor,reachCalls:nativeReachCallCount()-reach});}
const timings=[];if(${!process.argv.includes('--edges-only')}){const c=cases[1],input=JSON.parse(readFile(c.input)),expected=readFile(c.expected);for(const mode of ['cache','reach']){globalThis.DisableNativeReach=mode==='cache';if(serial(FootIKFloorCourse.run(input,c.angle))!==expected)throw Error('Warmup mismatch');}
for(const mode of ['cache','reach','reach','cache']){globalThis.DisableNativeReach=mode==='cache';const start=nativeThreadMilliseconds(),floor=nativeFloorCallCount(),reach=nativeReachCallCount(),model=FootIKFloorCourse.run(input,c.angle),cpuMs=nativeThreadMilliseconds()-start;if(serial(model)!==expected)throw Error('Timed mismatch');timings.push({mode,cpuMs,floorCalls:nativeFloorCallCount()-floor,reachCalls:nativeReachCallCount()-reach});}}
print(JSON.stringify({passed:true,exactReachQueries:checks,rejectedWithoutPublication:rejected,fullFrames:frames,fullCheckpoints:checkpoints,seededMaterialContactFrames:pinned,cases:rows,timings}));})();`);
if(process.argv.includes('--write-only')){console.log('Saved reach proof scripts ready');process.exit(0);}
const probe=process.env.FOOTIK_REACH_PROBE||path.join(dir,'../math-build/Release/footik_v8_probe.exe');
const child=cp.spawnSync(probe,[candidate,path.join(floorDir,'packaged-course.js'),setup,script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.join(root,'Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
if(child.error||child.status!==0)throw child.error||Error(child.stderr||child.stdout);
const report=JSON.parse(child.stdout);report.runtimeSha=crypto.createHash('sha256').update(runtime).digest('hex');if(report.timings.length){const mean=m=>report.timings.filter(t=>t.mode===m).reduce((n,t)=>n+t.cpuMs,0)/2;report.cacheCpuMs=mean('cache');report.reachCpuMs=mean('reach');report.speedup=report.cacheCpuMs/report.reachCpuMs;}
fs.writeFileSync(path.join(dir,process.argv.includes('--edges-only')?'edges.json':'proof.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
