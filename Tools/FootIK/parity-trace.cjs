'use strict';
// Isolated instrumentation; never edits the canonical solver or shipped bundle.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),options=process.argv.slice(2),option=(name,fallback)=>options.find(x=>x.startsWith('--'+name+'='))?.slice(name.length+3)||fallback;
const folder=path.join(root,'Saved/Diagnostics/FootIKPort20261030'),corpus=path.join(folder,option('corpus','wall-first-divergence'));
const probe=path.resolve(root,option('probe','Saved/Diagnostics/BodyflipPort20261030/chakra-build/Release/bodyflip_chakra_probe.exe'));
const item=JSON.parse(fs.readFileSync(path.join(corpus,'manifest.json'))).cases[0];
let runtime=fs.readFileSync(path.join(root,'Content/FootIKLab/Runtime.js'),'utf8');
const from='copy.finish(c, held);',to='if(Math.abs(context.time-1.7666666666666666)<1e-8)globalThis.__trace.push({k,context:c,supports:supports.map(h=>({point:h.point,id:h.surface.id,distance:length(sub(c.mass,h.point))})),held:held.length,threshold:height*1.2,snapshot:copy.snapshot()}); copy.finish(c, held);';
if(runtime.split(from).length!==2)throw Error('Unexpected forecast trace seam');runtime=runtime.replace(from,to);
const file=path.join(folder,'trace-runtime.js');fs.writeFileSync(file,runtime);
const script=path.join(folder,'trace-probe.js');
fs.writeFileSync(script,`var __trace=[];var input=JSON.parse(readFile(${JSON.stringify(path.join(corpus,item.input))}));var i=0,replies=input.policySteps;delete input.policySteps;input.coupled=true;globalThis.__footikNN=function(){return JSON.stringify(replies[i++]);};FootIKNative.command(JSON.stringify(input));print(JSON.stringify(__trace));`);
const shim=path.join(root,'Tools/FootIK/deterministic-math.js'),nodeProbe="const fs=require('fs'),vm=require('vm');global.readFile=p=>fs.readFileSync(p,'utf8');global.print=console.log;for(const p of process.argv.slice(1))vm.runInThisContext(fs.readFileSync(p,'utf8'),{filename:p});";
for(const engine of ['node','jsrt']){const run=spawnSync(engine==='node'?process.execPath:probe,engine==='node'?['-e',nodeProbe,file,script]:[shim,file,script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:180000,maxBuffer:8e6});if(run.status!==0)throw Error(run.error||run.stdout||run.stderr);const data=JSON.parse(run.stdout);fs.writeFileSync(path.join(folder,'trace-'+engine+'.json'),JSON.stringify(data,null,2));console.log(engine,data.length);}
const expected=JSON.parse(fs.readFileSync(path.join(folder,'trace-node.json'))),actual=JSON.parse(fs.readFileSync(path.join(folder,'trace-jsrt.json')));
for(let i=0;i<expected.length;i++){const a=actual[i],e=expected[i],dv=a.context.velocity.map((x,k)=>x-e.context.velocity[k]);if(a.held!==e.held||dv.some(x=>Math.abs(x)>1e-8)||a.snapshot.lastSupportTime!==e.snapshot.lastSupportTime)console.log(JSON.stringify({i,k:e.k,node:{held:e.held,lastSupportTime:e.snapshot.lastSupportTime,time:e.context.time,velocity:e.context.velocity,supports:e.supports},jsrt:{held:a.held,lastSupportTime:a.snapshot.lastSupportTime,time:a.context.time,velocity:a.context.velocity,supports:a.supports},dv}));}
