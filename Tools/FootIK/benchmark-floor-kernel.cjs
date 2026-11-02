'use strict';
// Run after verify-floor-kernel.cjs. Same V8 process, ABBA order; exclude wire
// serialization and comparison from the measured planner computation.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'Saved/Diagnostics/FootIKPort20261030/floor-native');
const oracle=fs.readFileSync(path.join(dir,'oracle-live-terrain.cjs'),'utf8');
fs.writeFileSync(path.join(dir,'oracle-in-v8.js'),"globalThis.FootIKFloorOracle=(function(){const module={exports:{}};const require=name=>FootIKRequire(name.split('/').pop());\n"+oracle+"\nreturn module.exports;})();");
const input=path.join(dir,'walk-stairs-37.input.json'),expected=path.join(dir,'walk-stairs-37.expected.json');
fs.writeFileSync(path.join(dir,'same-v8-timing.js'),`(function(){const input=JSON.parse(readFile(${JSON.stringify(input)})),expected=readFile(${JSON.stringify(expected)}),replace=(k,v)=>Object.is(v,-0)?'__negative_zero__':v,rows=[];for(const mode of ['before','native','native','before']){const calls=nativeFloorCallCount(),start=Date.now(),cpu=nativeThreadMilliseconds();const model=FootIKFloorCourse.run(input,37,mode==='before'?FootIKFloorOracle:undefined);const row={mode,cpuMs:nativeThreadMilliseconds()-cpu,wallMs:Date.now()-start,nativeCalls:nativeFloorCallCount()-calls};if((mode==='before')!==(!row.nativeCalls))throw Error('Wrong measured branch');if(JSON.stringify(model,replace)!==expected)throw Error('Timing replay changed frames/checkpoint');rows.push(row);}print(JSON.stringify({passed:true,source:'same packaged V8, ABBA order, solve excludes JSON comparison',rows}));})();`);
const result=cp.spawnSync(path.join(dir,'../math-build/Release/footik_v8_probe.exe'),[path.join(root,'Content/FootIKLab/Runtime.js'),path.join(dir,'packaged-course.js'),path.join(dir,'oracle-in-v8.js'),path.join(dir,'same-v8-timing.js')],{cwd:root,encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.join(root,'Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
if(result.error||result.status!==0)throw result.error||Error(result.stderr||result.stdout);
const report=JSON.parse(result.stdout),mean=mode=>report.rows.filter(r=>r.mode===mode).reduce((n,r)=>n+r.cpuMs,0)/2;
report.beforeCpuMs=mean('before');report.nativeCpuMs=mean('native');report.speedup=report.beforeCpuMs/report.nativeCpuMs;
fs.writeFileSync(path.join(dir,'same-v8-timing.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
