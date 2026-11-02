'use strict';
const fs=require('fs'),path=require('path'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'Saved/Diagnostics/FootIKPort20261030/native-v8');
if(process.versions.v8!=='13.6.233.17-node.51')throw Error('Pinned canonical V8 required');
let seed=7313;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;},rows=[];
for(let i=0;i<50000;i++){let x=(random()*2-1)*(i%3===0?1e6:i%3===1?10000:4);rows.push([x,Math.sin(x),Math.cos(x)]);}
for(let i=0;i<1000;i++){let x=(random()*2-1)*Math.pow(2,Math.floor(random()*2000-1000));rows.push([x,Math.sin(x),Math.cos(x)]);}
for(let n=-64;n<=64;n++)for(const d of [0,Number.EPSILON,-Number.EPSILON,1e-15,-1e-15,1e-8,-1e-8]){let x=n*Math.PI/2+d;rows.push([x,Math.sin(x),Math.cos(x)]);}
const input=path.join(out,'trig-input.json'),script=path.join(out,'trig-check.js');fs.writeFileSync(input,JSON.stringify(rows));
fs.writeFileSync(script,`var rows=JSON.parse(readFile(${JSON.stringify(input)})),different=0,first=[];for(var r of rows){for(var i=1;i<3;i++){var a=i===1?Math.sin(r[0]):Math.cos(r[0]);if(a!==r[i]){different++;if(first.length<5)first.push({x:r[0],fn:i,expected:r[i],actual:a});}}}print(JSON.stringify({samples:rows.length*2,different:different,first:first}));`);
const option=(key,def)=>process.argv.find(a=>a.startsWith('--'+key+'='))?.split('=').slice(1).join('=')||def;
const run=cp.spawnSync(path.join(root,'Saved/Diagnostics/FootIKPort20261030/math-build/Release/footik_v8_probe.exe'),[path.resolve(root,option('prelude',path.join(out,'trig-js.js'))),script],{encoding:'utf8',windowsHide:true,timeout:30000});if(run.status)throw Error(run.stderr);const report=JSON.parse(run.stdout);fs.writeFileSync(path.join(out,option('report','trig-expanded-parity.json')),JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(report.different)process.exitCode=1;
