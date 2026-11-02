'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),capture=JSON.parse(fs.readFileSync(path.join(directory,'root-support-capture.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.expected.json')));
global.__footikNN=()=>{throw Error('Root virtual transport must not call NN');};vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
const C=require('../../Labs/FootIKLab/surface-coupling.js'),R=require('../../Labs/FootIKLab/recovery.js'),command=value=>JSON.parse(global.FootIKNative.command(JSON.stringify(value))),p=capture.parameters;
const extent=Math.max(28,p.speed*p.duration+.5*Math.abs(p.gravity)*p.duration**2+2*p.height),context=r=>({base:r.position,surfaceQ:r.gaitRotation});
const virtual=[[0,0,0]];for(let i=1;i<capture.records.length;i++)virtual.push(R.add(virtual[i-1],C.transport(context(capture.records[i-1].context),context(capture.records[i].context))));
const start=performance.now(),cpu=process.cpuUsage();let status=command({op:'rootInit',canonicalTerrain:true,settings:p.s,height:p.height,speed:p.speed,gravity:p.gravity,extent}),windows=0;
for(let i=0;i<capture.records.length;i++){
 assert.deepEqual(status.virtualRoot,virtual[i],'virtual transport tick'+i);
 const wi=expected.windows.findIndex(w=>Math.round(w.frame*2)===i);
 if(wi>=0){
  const forecast=capture.forecasts.find(x=>x.tick===i&&x.ticks===40),request=expected.requests[wi],before=JSON.stringify(status.virtualRoot),result=command({op:'rootForecast',supports:forecast.supports,rootYawDegrees:request.rootYawDegrees.slice(0,10)});
  assert.deepEqual(result.virtualRoots,request.roots.slice(0,10),'actual NN root window'+wi);assert.deepEqual(result.rootYawDegrees,request.rootYawDegrees.slice(0,10));assert.equal(JSON.stringify(command({op:'rootStatus'}).virtualRoot),before);windows++;
 }
 status=command({op:'rootStep',ticks:1,supports:capture.records[i].supports});
}
command({op:'rootClose'});const used=process.cpuUsage(cpu),report={passed:true,ticks:capture.records.length,actualNNWindows:windows,virtualRootErrorM:0,futureVirtualRootErrorM:0,headingErrorDegrees:0,forecastNoVirtualMutation:true,rootOnlyCpuMilliseconds:(used.user+used.system)/1000,rootOnlyWallMilliseconds:performance.now()-start};
fs.writeFileSync(path.join(directory,'root-virtual.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
