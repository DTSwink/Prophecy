'use strict';
// Complete-pose/checkpoint and exact mutable-input proof for the one-entry
// cache. Existing independent floor oracles are reused; no new large dumps.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'Saved/Diagnostics/FootIKPort20261030/floor-native'),hash=text=>crypto.createHash('sha256').update(text).digest('hex');
const runtime=fs.readFileSync(path.join(root,'Content/FootIKLab/Runtime.js'),'utf8'),helper=fs.readFileSync(path.join(__dirname,'native-terrain-floor.cjs'),'utf8');
const timingOnly=process.argv.includes('--timing-only');
const begin=runtime.indexOf('"native-terrain-floor.cjs": function('),end=runtime.indexOf('\n    "',begin+1);if(begin<0||end<0)throw Error('Native helper factory changed');
const oldFactory=runtime.slice(begin,end),bodyStart=oldFactory.indexOf('{')+1,bodyEnd=oldFactory.lastIndexOf('}');
const candidate=runtime.slice(0,begin)+'"native-terrain-floor.cjs": function(module,exports,require2){\n'+helper+'\n    },'+runtime.slice(end),candidatePath=path.join(dir,'Runtime.cache.js');fs.writeFileSync(candidatePath,candidate);
const beforeHelper=path.join(dir,'before-cache-helper.js');if(!fs.existsSync(beforeHelper))fs.writeFileSync(beforeHelper,oldFactory.slice(bodyStart,bodyEnd));
const live=fs.readFileSync(path.join(__dirname,'live-terrain.cjs'),'utf8'),oldHelper=fs.readFileSync(beforeHelper,'utf8'),oracle=fs.readFileSync(path.join(dir,'oracle-live-terrain.cjs'),'utf8');
const setup=path.join(dir,'cache-check-setup.js');fs.writeFileSync(setup,`globalThis.BeforeFloorLive=(function(){const m={exports:{}};(function(module,exports){${oldHelper}})(m,m.exports);const module={exports:{}},require=name=>name.includes('native-terrain-floor')?m.exports:FootIKRequire(name.split('/').pop());${live}\nreturn module.exports;})();globalThis.OracleFloorLive=(function(){const module={exports:{}},require=name=>FootIKRequire(name.split('/').pop());${oracle}\nreturn module.exports;})();`);
const cases=[['walk-stairs',0],['walk-stairs',37],['run-stairs',90],['walk-down',-135],['run-down',37],['walk-flat',90]].map(([name,angle])=>({id:name+'-'+angle,angle,input:path.join(dir,name+'-'+angle+'.input.json'),expected:path.join(dir,name+'-'+angle+'.expected.json')}));
const script=path.join(dir,'cache-check.js');fs.writeFileSync(script,`(function(){
const Live=FootIKRequire('live-terrain.cjs'),helper=FootIKRequire('native-terrain-floor.cjs'),replace=(k,v)=>Object.is(v,-0)?'__negative_zero__':v;
const snapshot={tiles:[{id:'tile',point:[0,0,0],u:[1,0,0],v:[0,0,1],bounds:[-1,1,-1,1],shaped:true}]},terrain=Live.create(snapshot),oracle=OracleFloorLive.create(snapshot);
let checks=0;function check(p,o,expectedCalls){const before=nativeFloorCallCount(),actual=terrain.floorFor(p,o),expected=oracle.floorFor(p,o),calls=nativeFloorCallCount()-before;if(!Object.is(actual,expected))throw Error('Cached floor differs');if(expectedCalls!==undefined&&calls!==expectedCalls)throw Error('Wrong cache behavior '+checks+': '+calls+' vs '+expectedCalls);checks++;}
const shoe=[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>[x*.1,y*.04,z*.2]))),point=[0,.15,0];
check(point,shoe,1);check(point,shoe,0);check(point.slice(),shoe.map(p=>p.slice()),0);
shoe[0][1]-=.01;check(point,shoe,1);check(point,shoe,0);shoe[0][1]+=.01;check(point,shoe,1);
point[0]=-0;check(point,shoe,1);check(point,shoe,0);point[0]=0;check(point,shoe,1);
const signed=shoe.map(p=>p.slice());signed[0][0]=-0;check(point,signed,1);signed[0][0]=0;check(point,signed,1);check(point,signed,0);
check([3,.15,0],shoe,1);check([3,.15,0],shoe,0);check(point,shoe.concat(shoe),1);check(point,shoe.concat(shoe),0);check(point,[],1);check(point,[],0);
for(let i=0;i<40;i++){shoe[i%8][(i%5)%3]+=(i%2?-1:1)*.0001;check(point,shoe,1);check(point,shoe,0);}
check(point,Array.from({length:72},(_,i)=>shoe[i%8]),0);check(point,shoe,0);
const invalid=shoe.map(p=>p.slice());invalid[0][0]=NaN;check(point,invalid,0);check(point,shoe,0);
const empty=Live.create({tiles:[]});for(const [zero,wantedCalls] of [[-0,1],[-0,0],[0,1],[0,0],[-0,1]]){const calls=nativeFloorCallCount(),actual=empty.floorFor([0,zero,0],[]);if(!Object.is(actual,zero)||nativeFloorCallCount()-calls!==wantedCalls)throw Error('Signed output zero cache mismatch');checks++;}
const rows=[],cases=${JSON.stringify(cases)};let frames=0,checkpoints=0,pinned=0;
for(const c of ${timingOnly?'[]':'cases'}){const input=JSON.parse(readFile(c.input)),start=nativeThreadMilliseconds(),calls=nativeFloorCallCount(),model=FootIKFloorCourse.run(input,c.angle),cpuMs=nativeThreadMilliseconds()-start;if(JSON.stringify(model,replace)!==readFile(c.expected))throw Error(c.id+' complete frame/checkpoint difference');const n=model.frames.length+(model.seeded?.frames.length||0);frames+=n;checkpoints+=1+(model.seeded?1:0);pinned+=model.seeded?.materialPins||0;rows.push({id:c.id,frames:n,cpuMs,nativeCalls:nativeFloorCallCount()-calls});}
const c=cases[1],input=JSON.parse(readFile(c.input)),expected=readFile(c.expected),timings=[];
for(const mode of ['before','cache']){const model=FootIKFloorCourse.run(input,c.angle,mode==='before'?BeforeFloorLive:Live);if(JSON.stringify(model,replace)!==expected)throw Error('Warmup motion mismatch');}
for(const mode of ['before','cache','cache','before']){const cpu=nativeThreadMilliseconds(),calls=nativeFloorCallCount(),model=FootIKFloorCourse.run(input,c.angle,mode==='before'?BeforeFloorLive:Live),cpuMs=nativeThreadMilliseconds()-cpu;if(JSON.stringify(model,replace)!==expected)throw Error('Timing motion mismatch');timings.push({mode,cpuMs,nativeCalls:nativeFloorCallCount()-calls});}
print(JSON.stringify({passed:true,mutationSignedZeroAndFallbackChecks:checks,fullFrames:frames,fullCheckpoints:checkpoints,seededMaterialContactFrames:pinned,cases:rows,timings}));})();`);
const child=cp.spawnSync(path.join(dir,'../math-build/Release/footik_v8_probe.exe'),[candidatePath,path.join(dir,'packaged-course.js'),setup,script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.join(root,'Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
if(child.error||child.status!==0)throw child.error||Error(child.stderr||child.stdout);
let report=JSON.parse(child.stdout);if(timingOnly){const previous=JSON.parse(fs.readFileSync(path.join(dir,'cache-proof.json')));if(previous.helperSha256!==hash(helper))throw Error('Full-pose proof required for changed helper');report={...previous,timings:report.timings,mutationSignedZeroAndFallbackChecks:report.mutationSignedZeroAndFallbackChecks};}const mean=mode=>report.timings.filter(v=>v.mode===mode).reduce((n,v)=>n+v.cpuMs,0)/2;report.beforeCpuMs=mean('before');report.cacheCpuMs=mean('cache');report.speedup=report.beforeCpuMs/report.cacheCpuMs;report.warmedComparison=true;report.helperSha256=hash(helper);report.candidateRuntimeSha256=hash(candidate);fs.writeFileSync(path.join(dir,'cache-proof.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
