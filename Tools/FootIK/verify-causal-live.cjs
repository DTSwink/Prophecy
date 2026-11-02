'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.expected.json'))),capture=JSON.parse(fs.readFileSync(path.join(directory,'root-support-capture.json')));
let requests=[];global.__footikNN=text=>{const request=JSON.parse(text);requests.push(request);return JSON.stringify({pose:request.seeds?.[1]||requests[0].seeds[1]});};
vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
const K=require('../../Labs/FootIKLab/footik.js'),R=require('../../Labs/FootIKLab/recovery.js'),command=value=>JSON.parse(global.FootIKNative.command(JSON.stringify(value))),run=K.decode(input.source,input.parents),start=performance.now(),cpu=process.cpuUsage();
const fields=f=>({pose:{points:f.pose.points,q:f.pose.q},root:f.root,feet:f.feet,surface:f.surface,slide:f.slide,pelvisOffset:f.pelvisOffset,influence:f.influence});
let frames=0,handoffs=0;const entry=capture.records.findIndex(r=>r.context.slide);
function expectedResume(source,at,original,virtual){const angle=(K.commandYaw(input.settings,at,run.directionMeta.commandSpeed)-K.commandYaw(input.settings,original,run.directionMeta.commandSpeed))*Math.PI/180,turn=R.qexp([0,angle,0]),q=source.q.map(v=>R.qm(turn,v));return {points:source.points.map(v=>R.add(virtual,R.rotate(turn,R.sub(v,source.points[0])))),q,axes:q.map(R.toAxes)};}
if(!process.argv.includes('--seed-only')){
 const p=capture.parameters,extent=Math.max(28,p.speed*p.duration+.5*Math.abs(p.gravity)*p.duration**2+2*p.height);
 command({op:'init',source:input.source,parents:input.parents,settings:p.s,height:p.height,speed:p.speed,canonicalTerrain:true,extent,policySteps:input.policySteps});
 for(let i=0;i<expected.frames.length;){
  const count=Math.min(4,expected.frames.length-i),result=command({op:'tick',ticks:count});assert.equal(result.tick,i+count);assert.equal(result.frames.length,count);assert.equal(result.outputs.length,count);
  for(let k=0;k<count;k++){
   assert.deepEqual(fields(result.frames[k]),fields(expected.frames[i+k]),'canonical causal frame'+(i+k));
   assert.deepEqual(result.outputs[k].supports,capture.records[i+k].supports,'same-tick support'+(i+k));
   assert.deepEqual(result.outputs[k].root.position,capture.records[i+k].context.position,'same-tick root'+(i+k));frames++;
  }
  i+=count;
  if(i>=8&&i%32===0){const at=i-1,read=command({op:'policyHandoff'});assert.deepEqual(command({op:'policyHandoff'}),read,'policy handoff is read-only');
   const current=capture.commands[at].pose,previous=capture.commands[at-4].pose,paused=at>=entry;
   const wanted=paused?expectedResume(capture.commands[entry].pose,at/120,entry/120,current.points[0]):current;
   const old=paused?expectedResume(capture.commands[entry-4].pose,at/120-1/30,entry/120-1/30,previous.points[0]):previous;
   assert.deepEqual(read.current,wanted,'clean current policy history at'+at);assert.deepEqual(read.previous,old,'clean previous policy history at'+at);assert.deepEqual(read.root,capture.records[at].context.position);assert.deepEqual(read.previousRoot,capture.records[at-4].context.position);assert.equal(read.sliding,paused);handoffs++;
  }
 }
 command({op:'close'});
}
// Actual current/history takeover at tick0: no warmup, previous-pose display,
// or made-up pin flags. Native policy sees the supplied pair unchanged.
const previous=run.poses[0],current=run.poses[1],initialPair={previous,current};requests=[];
command({op:'init',source:input.source,parents:input.parents,initialPair,settings:{...input.settings,terrain:'flat',inclineGravity:false,slide:false,enabled:false},height:run.referenceHeight,root:{position:[0,0,0],velocity:[0,0,2],normal:[0,1,0]},travelVelocity:[0,0,2],surfaces:[{id:'floor',origin:[0,0,0],normal:[0,1,0],tangent:[1,0,0],bounds:[-20,20,-20,20]}]});
const first=command({op:'tick',ticks:4});assert.equal(requests.length,1);assert.deepEqual(requests[0].seeds,[previous,current].map(p=>({points:p.points,axes:p.axes})));assert.deepEqual(requests[0].roots[0],previous.points[0]);assert.deepEqual(requests[0].roots[1],current.points[0]);assert.deepEqual(first.outputs[0].source,current);assert.equal(first.outputs.length,4);assert.equal(first.tick,4);
const initialRead=command({op:'policyHandoff'});assert.equal(initialRead.tick,3);assert.equal(initialRead.previous.points.length,26);assert.equal(requests.length,1);assert.deepEqual(initialRead.current,first.outputs[3].source);handoffs++;
assert.throws(()=>command({op:'tick',ticks:1,root:{position:[1,0,0]}}),/explicit teleport/);
command({op:'close'});assert.throws(()=>command({op:'policyHandoff'}),/disabled/);const used=process.cpuUsage(cpu),report={passed:true,canonicalFrames:frames,measuredSeedExact:true,firstRequestTick:0,sameTickRootSupport:true,outputsPer30HzInterval:4,readOnlyPolicyHandoffs:handoffs,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-start};
fs.writeFileSync(path.join(directory,'causal-live.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
