'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.expected.json'))),capture=JSON.parse(fs.readFileSync(path.join(directory,'root-support-capture.json')));
global.__footikNN=()=>{throw Error('External-root surface solver may not call NN');};vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
const command=value=>JSON.parse(global.FootIKNative.command(JSON.stringify(value))),p=capture.parameters,extent=Math.max(28,p.speed*p.duration+.5*Math.abs(p.gravity)*p.duration**2+2*p.height),start=performance.now(),cpu=process.cpuUsage();
command({op:'liveSurfaceInit',source:input.source,parents:input.parents,settings:p.s,height:p.height,speed:p.speed,canonicalTerrain:true,extent,rootFrames:capture.records.map(r=>r.context)});
const fields=f=>({pose:{points:f.pose.points,q:f.pose.q},root:f.root,feet:f.feet,surface:f.surface,slide:f.slide,pelvisOffset:f.pelvisOffset,influence:f.influence});
let supports=0;
for(let i=0;i<expected.frames.length;i++){
 const sourceCommand=process.argv.includes('--infer-intent')?{pose:capture.commands[i].pose}:capture.commands[i];
 const result=command({op:'liveSurfaceStep',currentTick:i,commands:[sourceCommand],rootReceipt:capture.records[i].receipt});
 assert.deepEqual(fields(result.frame),fields(expected.frames[i]),'full external-root frame'+i);assert.deepEqual(result.supports,capture.records[i].supports,'root feedback supports'+i);supports+=result.supports.length;
}
command({op:'liveSurfaceClose'});assert.equal(command({op:'liveSurfaceStatus'}).enabled,false);
const used=process.cpuUsage(cpu),report={passed:true,frames:expected.frames.length,allPoseAndContactFieldsExact:true,supportFeedbackSamples:supports,rootIntegrationCalls:0,nnCalls:0,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-start};
fs.writeFileSync(path.join(directory,'external-surface.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
