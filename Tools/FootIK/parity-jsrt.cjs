'use strict';
// Exercise the Windows JS engine before starting an Unreal build. The reference
// is generated independently by parity-export.cjs from unbundled lab modules.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
try{const os=require('node:os');os.setPriority(0,process.env.FOOTIK_DIAG_NORMAL_PRIORITY?os.constants.priority.PRIORITY_NORMAL:os.constants.priority.PRIORITY_BELOW_NORMAL);}catch{}
const root=path.resolve(__dirname,'../..'),args=process.argv.slice(2);
const arg=(key,fallback)=>args.find(a=>a.startsWith(`--${key}=`))?.slice(key.length+3)||fallback;
const corpus=path.resolve(root,arg('corpus','Saved/Diagnostics/FootIKPort20261030'));
const diagnostic=args.includes('--diagnostic'),engine=arg('engine','jsrt');
const runtime=path.resolve(root,arg('runtime','Content/FootIKLab/Runtime.js'));
const prelude=arg('prelude','');
const probe=path.resolve(root,arg('probe','Saved/Diagnostics/BodyflipPort20261030/chakra-build/Release/bodyflip_chakra_probe.exe'));
const manifest=JSON.parse(fs.readFileSync(path.join(corpus,'manifest.json'))),filter=arg('case',''),reports=[];
const reportFile=path.join(corpus,arg('report',`${engine}-parity${diagnostic?'-diagnostic':''}.json`));
const save=complete=>fs.writeFileSync(reportFile,JSON.stringify({passed:complete&&reports.every(r=>r.passed),complete,engine:engine==='node'?'Node V8':engine==='v8'?'Embedded V8':'Windows Chakra JSRT',reports},null,2));
for(const item of manifest.cases.filter(c=>!filter||new RegExp(filter).test(c.name))){
 const input=path.join(corpus,item.input),expected=path.join(corpus,item.expected);
 const script=`(function(){
 var input=JSON.parse(readFile(${JSON.stringify(input)})), expected=JSON.parse(readFile(${JSON.stringify(expected)}));
 var frames=0,numbers=0,maxNumber=0,maxNumberPath='',maxPosition=0,maxPositionPath='',maxQuaternion=0,maxQuaternionComponent=0,quaternionComponentsDifferent=0,failed=0,failures=[];
 function fail(p,m){failed++;if(failures.length<20)failures.push(p+': '+m);if(!${diagnostic})throw Error(p+': '+m);}
 function compare(a,e,p){
  if(e===null){if(a!==null)fail(p,'null differs');return;}
  if(typeof a!==typeof e)fail(p,'type differs');
  if(typeof e==='number'){var d=Math.abs(a-e);numbers++;if(d>maxNumber){maxNumber=d;maxNumberPath=p;}if(d>1e-8)fail(p,'number '+d);return;}
  if(typeof e!=='object'){if(a!==e)fail(p,'value differs');return;}
  if(Array.isArray(e)){
   if(!Array.isArray(a)||a.length!==e.length)fail(p,'array length');
   if(/\\.pose\\.(points|q)$/.test(p)){
    var q=/\\.q$/.test(p),width=q?4:3;
    for(var b=0;b<e.length;b++){if(a[b].length!==width)fail(p,'bone width');var sum=0;for(var k=0;k<width;k++){var x=a[b][k],y=e[b][k];if(q){maxQuaternionComponent=Math.max(maxQuaternionComponent,Math.abs(x-y));if(x!==y)quaternionComponentsDifferent++;}sum+=q?x*y:(x-y)*(x-y);numbers++;}var error=q?Math.abs(1-Math.abs(sum)):Math.sqrt(sum);if(q)maxQuaternion=Math.max(maxQuaternion,error);else if(error>maxPosition){maxPosition=error;maxPositionPath=p+'['+b+']';}if(error>(q?1e-10:1e-8))fail(p+'['+b+']','bone error '+error);}
   }else for(var i=0;i<e.length;i++)compare(a[i],e[i],p+'['+i+']');
  }else Object.keys(e).forEach(function(k){if(!Object.prototype.hasOwnProperty.call(a,k))fail(p+'.'+k,'missing');compare(a[k],e[k],p+'.'+k);});
 }
 function command(value){return JSON.parse(FootIKNative.command(JSON.stringify(value)));}
 var replies=input.policySteps||(input.handoffReply?[input.handoffReply]:null),requestIndex=0;
 if(replies){if(input.policySteps){delete input.policySteps;input.coupled=true;}delete input.handoffReply;globalThis.__footikNN=function(text){var request=JSON.parse(text),i=requestIndex++;if(!replies[i]||!expected.requests[i])throw Error('Unexpected policy callback '+i);compare(request,expected.requests[i],'requests['+i+']');return JSON.stringify(replies[i]);};}
 var start=Date.now(),prepared=command(input);compare(prepared.events,expected.events,'events');
 for(var offset=0;offset<expected.frames.length;offset+=24){var count=Math.min(24,expected.frames.length-offset),batch=command({op:'frames',start:offset,count:count});if(batch.frames)batch=batch.frames;if(batch.length!==count)fail('frames','batch size');for(var i=0;i<count;i++)compare(batch[i],expected.frames[offset+i],'frame['+(offset+i)+']');frames+=count;}
 var windows=command({op:'windows'});if(windows.windows)windows=windows.windows;compare(windows,expected.windows,'windows');if(requestIndex!==expected.requests.length)fail('requests','callback count');command({op:'close'});
 print(JSON.stringify({passed:failed===0,name:${JSON.stringify(item.name)},frames:frames,windows:windows.length,numbers:numbers,maxNumber:maxNumber,maxNumberPath:maxNumberPath,maxPosition:maxPosition,maxPositionPath:maxPositionPath,maxQuaternion:maxQuaternion,maxQuaternionComponent:maxQuaternionComponent,quaternionComponentsDifferent:quaternionComponentsDifferent,failed:failed,failures:failures,jsrtMs:Date.now()-start}));
})();`;
 const scriptFile=path.join(corpus,'jsrt-probe.js');fs.writeFileSync(scriptFile,script);
 // This is an owned subprocess. Its real globals avoid vm.Context's global
 // proxy penalty, which is unrelated to the packaged solver's actual cost.
 const nodeProbe="const fs=require('fs'),vm=require('vm');global.readFile=p=>fs.readFileSync(p,'utf8');global.print=console.log;const wall=Date.now();for(const p of process.argv.slice(1))vm.runInThisContext(fs.readFileSync(p,'utf8'),{filename:p});const cpu=process.cpuUsage();console.error('PROBE_METRICS '+JSON.stringify({cpuMs:(cpu.user+cpu.system)/1000,wallMs:Date.now()-wall,peakBytes:process.resourceUsage().maxRSS*1024}));";
 const scripts=[...(prelude?[path.resolve(root,prelude)]:[]),runtime,scriptFile];
 const run=spawnSync(engine==='node'?process.execPath:probe,engine==='node'?['-e',nodeProbe,...scripts]:scripts,{cwd:root,encoding:'utf8',windowsHide:true,maxBuffer:1024*1024,timeout:180000});
 if(run.error||run.status!==0){const error=String(run.error||run.stderr||run.stdout);reports.push({passed:false,name:item.name,error});save(false);throw Error(`${item.name}: ${error}`);}
 const report=JSON.parse(run.stdout.trim()),metrics=run.stderr.match(/PROBE_METRICS (\{[^\n]+\})/);if(metrics)report.process=JSON.parse(metrics[1]);reports.push(report);save(false);console.log(JSON.stringify(report));
}
if(!reports.length)throw Error('No parity cases matched');
const passed=reports.every(r=>r.passed);
save(true);
if(!passed)process.exitCode=1;
