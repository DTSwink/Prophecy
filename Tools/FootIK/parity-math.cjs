'use strict';
// Diagnose host Math differences without running a solver or changing Math.
// Differences here are evidence, not proof of the first divergent solver branch.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),folder=path.join(root,'Saved/Diagnostics/FootIKPort20261030');fs.mkdirSync(folder,{recursive:true});
if(process.versions.v8!=='13.6.233.17-node.51')throw Error('Math reference requires pinned V8 13.6.233.17-node.51; got '+process.versions.v8);
const options=process.argv.slice(2),option=(name,fallback)=>options.find(x=>x.startsWith('--'+name+'='))?.slice(name.length+3)||fallback;
let seed=0x718f2a3c;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;},rows=[];
for(let i=0;i<2048;i++){
 const x=random()*2-1,y=random()*2-1,z=random()*2-1,w=random()*2-1;
 for(const [name,args] of [['hypot',[x,y]],['hypot',[x,y,z]],['hypot',[x,y,z,w]],['hypot',[x,y,z,w,x*y,y*z,z*w]],['sin',[x*Math.PI]],['cos',[x*Math.PI]],['acos',[x]],['asin',[x]],['atan',[x*20]],['atan2',[x,y]],['tan',[x]],['exp',[x*4]],['log',[Math.abs(x)+.001]],['log1p',[x*.999]],['sqrt',[x*x+y*y]],['pow',[Math.abs(x)+.001,Math.abs(y)*4]],['pow',[x*1e5,2]],['pow',[Math.abs(x),.5]]])rows.push({name,args,value:Math[name](...args)});
}
const input=path.join(folder,'math-input.json'),script=path.join(folder,'math-probe.js');fs.writeFileSync(input,JSON.stringify(rows));
fs.writeFileSync(script,`var rows=JSON.parse(readFile(${JSON.stringify(input)})),stats={};for(var i=0;i<rows.length;i++){var r=rows[i],k=r.name+'/'+r.args.length,a=Math[r.name].apply(Math,r.args),s=stats[k]||(stats[k]={count:0,different:0,maxAbsolute:0,maxRelative:0});s.count++;if(a!==r.value)s.different++;s.maxAbsolute=Math.max(s.maxAbsolute,Math.abs(a-r.value));s.maxRelative=Math.max(s.maxRelative,Math.abs(a-r.value)/Math.max(1e-300,Math.abs(r.value)));}print(JSON.stringify({engine:'Windows Chakra JSRT',note:'Host Math implementation differences; solver branch causality not established.',stats:stats}));`);
const probe=path.resolve(root,option('probe','Saved/Diagnostics/BodyflipPort20261030/chakra-build/Release/bodyflip_chakra_probe.exe')),prelude=option('prelude',''),run=spawnSync(probe,[...(prelude?[path.resolve(root,prelude)]:[]),script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:10000});
if(run.status!==0)throw Error(run.error||run.stderr||run.stdout);const report=JSON.parse(run.stdout);fs.writeFileSync(path.join(folder,option('report','math-differences.json')),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
