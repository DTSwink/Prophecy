'use strict';
// Exercise typed-array offsets, exact signed-zero results and repeated handle
// ownership without starting an Unreal editor or changing the lab sources.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),bin=fs.readFileSync(path.join(dir,'current-yaw-stop10.entry-fit.bin'));
if(bin.toString('ascii',0,8)!=='FIKENT01')throw Error('Invalid fixture');
const inputs=bin.readUInt32LE(16),outputs=bin.readUInt32LE(20);let at=24;
const read=n=>Array.from({length:n},()=>{const v=bin.readDoubleLE(at);at+=8;return Object.is(v,-0)?'-0':String(v);}).join(',');
const legBin=fs.readFileSync(path.join(dir,'current-yaw-stop10.leg-contact.bin'));let legAt=24;
const legRead=n=>Array.from({length:n},()=>{const v=legBin.readDoubleLE(legAt);legAt+=8;return Object.is(v,-0)?'-0':String(v);}).join(',');
const legSource=`const legInput=new Float64Array([${legRead(legBin.readUInt32LE(16))}]),legExpected=[${legRead(legBin.readUInt32LE(20))}],legOutput=new Float64Array(33);if(!__footikLegContact(legInput,legOutput))throw Error('Valid leg rejected');for(let i=0;i<33;i++)if(!Object.is(legOutput[i],legExpected[i]))throw Error('Leg bits differ'+i);for(let i=0;i<10000;i++)if(__footikLegContact(shortInput,sentinel)!==0)throw Error('Invalid leg accepted');`;
const source=`(function(){const values=[${read(inputs)}],expected=[${read(outputs)}];
const storage=new Float64Array(values.length+4),input=storage.subarray(2,values.length+2);input.set(values);
const backing=new Float64Array(expected.length+6).fill(1234),output=backing.subarray(3,expected.length+3);
if(!__footikEntrySolve(input,output))throw Error('Valid view rejected');
for(let i=0;i<expected.length;i++)if(!Object.is(output[i],expected[i]))throw Error('Native entry bits differ at '+i);
if(backing[0]!==1234||backing[backing.length-1]!==1234)throw Error('Output exceeded view');
const shortInput=new Float64Array(2),sentinel=new Float64Array(3).fill(987);
for(let i=0;i<10000;i++)if(__footikEntrySolve(shortInput,sentinel)!==0)throw Error('Invalid input accepted');
if(!sentinel.every(x=>x===987))throw Error('Failure partially published');
${legSource}
print(JSON.stringify({passed:true,viewOffset:true,exactDoubles:expected.length+33,rejectedWithoutPublication:20000}));})();`;
const file=path.join(dir,'native-batch-buffer-smoke.js');fs.writeFileSync(file,source);
const env={...process.env,FOOTIK_DIAG_NORMAL_PRIORITY:'1',FOOTIK_V8_DLL:path.resolve(__dirname,'../../Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')};
const result=cp.spawnSync(path.join(dir,'math-build/Release/footik_v8_probe.exe'),[file],{encoding:'utf8',windowsHide:true,env,timeout:30000,maxBuffer:1024*1024});
if(result.error||result.status!==0)throw result.error||Error(result.stderr||result.stdout);
const report=JSON.parse(result.stdout),metrics=result.stderr.match(/PROBE_METRICS (\{[^\n]+\})/);if(metrics)report.process=JSON.parse(metrics[1]);
fs.writeFileSync(path.join(dir,'native-batch-buffer-smoke.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
