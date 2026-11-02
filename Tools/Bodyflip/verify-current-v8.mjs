import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const out=process.env.BODYFLIP_PORT_OUTPUT||'Saved/Diagnostics/BodyflipPort20261102';
const fixture=JSON.parse(fs.readFileSync(out+'/current-port-fixture.json'));
const runtime=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');
const nativeCases=['saved-pike','pike-front','pike-back','slashLU','sweepKick-twist','big-throw-twist','small-throw-twist','poses-and-keep'];
const cases=[...fixture.cases,...fixture.cases.filter(c=>nativeCases.includes(c.fixture.name)).map(c=>({...c,native:true}))];
const filter=process.argv.find(a=>a.startsWith('--case='))?.slice(7),selected=cases.filter(c=>!filter||c.fixture.name+(c.native?'-native-rig':'')===filter);
assert(selected.length,'No matching cases');
const reportFile=out+'/current-v8'+(filter?'-'+filter:'')+'.json';
const timeout=Number(process.env.BODYFLIP_V8_TIMEOUT_MS||180000);
const reports=[];let numbers=0,worst=0;
function compare(a,b,key){
 assert.equal(typeof a,typeof b,key);
 if(typeof a==='number'){assert(Number.isFinite(a)&&Number.isFinite(b),key);numbers++;const d=Math.abs(a-b);worst=Math.max(worst,d);assert(d<=1e-7+1e-10*Math.max(Math.abs(a),Math.abs(b)),key+': '+d);}
 else if(a===null||typeof a!=='object')assert.equal(a,b,key);
 else{assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),key);for(const k of Object.keys(a))compare(a[k],b[k],key+'.'+k);}
}
for(const c of selected){
 const name=c.fixture.name+(c.native?'-native-rig':''),script=`
globalThis.__bodyflipAttack=id=>readFile('Content/BodyflipLab/Attacks/'+id+'.json');
const B=BodyflipNative.raw;B({op:'assets',value:JSON.parse(readFile('Content/BodyflipLab/Assets.json'))});
B({op:'start',settings:${JSON.stringify(c.fixture.settings)},rigProfile:${c.native?"JSON.parse(readFile('Labs/BodyflipLab/fixtures/native-rig.json'))":'null'},horizon:${c.fixture.settings.trimOut}});
print(JSON.stringify(${JSON.stringify(c.fixture.times)}.map(time=>B({op:'sample',time}))));`;
 const file=out+'/'+name+'-v8.js';fs.writeFileSync(file,script);
 let expected=c.frames;
 if(c.native){let raw;const context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:v=>raw=v});vm.runInContext(runtime,context);vm.runInContext(script,context);expected=JSON.parse(raw);}
 const started=performance.now(),result=spawnSync('Saved/Diagnostics/FootIKPort20261030/math-build/Release/footik_v8_probe.exe',['Content/BodyflipLab/Runtime.js',file],{encoding:'utf8',timeout,maxBuffer:8e6,env:{...process.env,FOOTIK_V8_DLL:path.resolve('Content/FootIKLab/V8/ClearScriptV8.win-x64.dll'),BODYFLIP_PROBE_WATERMARK_MB:'384',BODYFLIP_PROBE_LIMIT_MB:'512'}});
 fs.writeFileSync(out+'/'+name+'-v8.log',result.stderr||'');assert.equal(result.status,0,name+': '+result.stderr);
 const actual=JSON.parse(result.stdout);compare(actual,expected,name);
 fs.writeFileSync(out+'/'+name+'-v8-frames.json',result.stdout);
 reports.push({name,frames:actual.length,seconds:(performance.now()-started)/1000});console.log(JSON.stringify(reports.at(-1)));
 fs.writeFileSync(reportFile,JSON.stringify({passed:reports.length===selected.length,runtime:JSON.parse(fs.readFileSync('Content/BodyflipLab/Receipt.json')).runtime,numbers,worst,reports},null,2));
}
