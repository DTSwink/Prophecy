// Replays the real native NN answers without Unreal/model initialization.
// This separates script CPU/heap costs from inference. It is diagnostic only;
// gameplay continues to call the live native NN adapter.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';

const dir='Saved/Diagnostics/BodyflipPort20261030',source=JSON.parse(fs.readFileSync(dir+'/approved-native.json','utf8'));
const settings=JSON.parse(fs.readFileSync('Labs/BodyflipLab/approved/2026-10-30/saved-profile.json','utf8')).settings;
const work=dir+'/approved-replay';fs.mkdirSync(work,{recursive:true});
const engine=process.argv.includes('--v8')?'v8':'chakra';
for(let i=0;i<source.nnCalls.length;i++)fs.writeFileSync(`${work}/nn-${i}.json`,JSON.stringify(source.nnCalls[i]));
const script=work+'/probe.js',through=Math.round(settings.trimOut*60);
fs.writeFileSync(script,`
${engine==='v8'?'globalThis.heap=()=>0;':''}
const settings=${JSON.stringify(settings)},calls=${source.nnCalls.length},end=${through};let cursor=0,maxRequestDifference=0,maxFloat32Difference=0;
const same=(a,b)=>{if(typeof a!==typeof b)return false;if(typeof a==='number'){maxRequestDifference=Math.max(maxRequestDifference,Math.abs(a-b));maxFloat32Difference=Math.max(maxFloat32Difference,Math.abs(Math.fround(a)-Math.fround(b)));return Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=1e-9&&Math.abs(Math.fround(a)-Math.fround(b))<=1e-9;}if(a===null||b===null||typeof a!=='object')return a===b;const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>Object.prototype.hasOwnProperty.call(b,k)&&same(a[k],b[k]));};
globalThis.__bodyflipAttack=id=>readFile('Content/BodyflipLab/Attacks/'+id+'.json');
globalThis.__bodyflipNN=request=>{if(cursor>=calls)throw Error('No recorded NN answer at call '+cursor);const row=JSON.parse(readFile('${work}/nn-'+cursor+'.json'));const a=JSON.parse(request),b=JSON.parse(row.request);if(!same(a,b)){print(JSON.stringify({error:'NN request differs at call '+cursor,maxRequestDifference,maxFloat32Difference}));throw Error('NN request differs at call '+cursor);}cursor++;if(row.error)throw Error(row.error);return row.reply;};
const command=BodyflipNative.command,measure=(name,input)=>{const t=Date.now(),result=JSON.parse(command(typeof input==='string'?input:JSON.stringify(input)));print(JSON.stringify({stage:name,seconds:(Date.now()-t)/1000,heapBytes:Number(heap()),nnCalls:cursor}));return result;};
try{
measure('assets','{"op":"assets","value":'+readFile('Content/BodyflipLab/Assets.json')+'}');
measure('start',{op:'start',settings,horizon:1/60});
measure('prepare '+end,{op:'prepare',time:end/60});
const frames=[];for(let n=0;n<=end;n++)frames.push(JSON.parse(command(JSON.stringify({op:'sample',time:n/60}))));
print(JSON.stringify({completed:true,frames,heapBytes:Number(heap()),nnCalls:cursor,maxRequestDifference,maxFloat32Difference}));
}catch(e){print(JSON.stringify({error:String(e),stack:e.stack,heapBytes:Number(heap()),nnCalls:cursor}));throw e;}
`);
const executable=engine==='v8'?'Saved/Diagnostics/FootIKPort20261030/math-build/Release/footik_v8_probe.exe':path.join(dir,'chakra-build/Release/bodyflip_chakra_probe.exe');
const begin=performance.now(),run=spawnSync(executable,['Content/BodyflipLab/Runtime.js',script],{encoding:'utf8',timeout:125000,maxBuffer:32*1024*1024,env:{...process.env,FOOTIK_V8_DLL:path.resolve('Content/FootIKLab/V8/ClearScriptV8.win-x64.dll'),BODYFLIP_PROBE_WATERMARK_MB:'384',BODYFLIP_PROBE_LIMIT_MB:'512'}});
fs.writeFileSync(`${work}/${engine}-stdout.log`,run.stdout||'');
const rows=run.stdout.trim().split(/\r?\n/).filter(Boolean).map(s=>{try{return JSON.parse(s);}catch{return {error:s};}}),last=rows.at(-1),stages=rows.filter(x=>x.stage);
const report={engine,nativePassed:source.passed,seconds:(performance.now()-begin)/1000,status:run.status,error:run.error?.message,errors:rows.filter(x=>x.error),stderr:run.stderr,stages,completed:!!last?.completed,maxRequestDifference:last?.maxRequestDifference,maxFloat32Difference:last?.maxFloat32Difference};
if(last?.completed&&source.passed){let position=0,quaternion=0;assert.equal(last.frames.length,source.frames.length);for(let f=0;f<last.frames.length;f++){const a=last.frames[f].pose,b=source.frames[f].pose;for(let i=0;i<a.points.length;i++){position=Math.max(position,Math.hypot(...a.points[i].map((v,k)=>v-b.points[i][k])));quaternion=Math.max(quaternion,1-Math.abs(a.q[i].reduce((s,v,k)=>s+v*b.q[i][k],0)));}}report.maxPosition=position;report.maxQuaternion=quaternion;assert(position<1e-7&&quaternion<1e-12,'Replay must preserve native poses');}
fs.writeFileSync(`${work}/${engine}-receipt.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
assert.equal(run.status,0,run.stderr||JSON.stringify(rows.at(-1)));assert(last?.completed,'Replay did not complete');
