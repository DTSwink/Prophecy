'use strict';
// Diagnostic requirement check: live causal stairs versus the accepted lab
// planner under the same measured root and NN pose. No inference is started.
// A finite output alone is not sufficient to call the live port 1:1.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..'),folder=path.join(root,'Saved/Diagnostics/FootIKPort20261030');
try{const os=require('node:os');os.setPriority(0,os.constants.priority.PRIORITY_BELOW_NORMAL);}catch{}
vm.runInThisContext(fs.readFileSync(path.join(root,'Content/FootIKLab/Runtime.js'),'utf8'));
const K=require('../../Labs/FootIKLab/footik.js'),R=require('../../Labs/FootIKLab/recovery.js');
const call=a=>JSON.parse(globalThis.FootIKNative.command(JSON.stringify(a))),reports=[];
for(const gait of ['walk','run']){
 const input=JSON.parse(fs.readFileSync(path.join(folder,`${gait}-stairs.input.json`))),run=K.decode(input.source,input.parents),reference=K.prepare(run,input.settings);
 const surfaces=reference.terrain.tiles.map(t=>({id:t.id,origin:[0,t.y,0],normal:[0,1,0],tangent:[1,0,0],bounds:[t.x0,t.x1,t.z0,t.z1],thickness:.2}));
 const navigation=y=>[{id:'authored-root-height',origin:[0,y,0],normal:[0,1,0],tangent:[1,0,0],bounds:[-100,100,-100,100],thickness:.2}];
 call({op:'init',source:input.source,parents:input.parents,settings:{...input.settings,slideEnabled:false},policy:false,height:.9,surfaces,rootSurfaces:navigation(reference.frames[0].root[1]),root:{position:reference.frames[0].root,velocity:[0,0,reference.speed],normal:[0,1,0],bodyRotation:[0,0,0,1],yaw:0}});
 let maxRoot=0,maxPosition=0,maxRotationDeg=0,worst=null,statesDiffer=0;
 for(let i=0;i<reference.frames.length;i++){
  const wanted=reference.frames[i],time=i/120,p=K.at(run,time),previous=reference.frames[Math.max(0,i-1)],velocity=R.mul(R.sub(wanted.root,previous.root),120);
  const actual=call({op:'tick',pose:p,root:{position:wanted.root,velocity,normal:[0,1,0],bodyRotation:[0,0,0,1],yaw:0},surfaces,rootSurfaces:navigation(wanted.root[1]),surfaceRevision:i,ticks:1,travelVelocity:velocity}).frame;
  maxRoot=Math.max(maxRoot,R.length(R.sub(actual.root,wanted.root)));
  for(let bone=0;bone<run.names.length;bone++){
   const error=R.length(R.sub(actual.pose.points[bone],wanted.pose.points[bone]));
   if(error>maxPosition){maxPosition=error;worst={frame:i/2,bone:run.names[bone],actual:actual.pose.points[bone],expected:wanted.pose.points[bone]};}
   maxRotationDeg=Math.max(maxRotationDeg,R.length(R.qlog(R.qm(actual.pose.q[bone],R.qinv(wanted.pose.q[bone]))))*180/Math.PI);
  }
  if(wanted.feet.some((f,side)=>f.state!==actual.feet[side].state))statesDiffer++;
 }
 call({op:'close'});reports.push({gait,frames:reference.frames.length,maxRootErrorM:maxRoot,maxPositionErrorM:maxPosition,maxRotationErrorDeg:maxRotationDeg,footStateMismatchFrames:statesDiffer,worst});
}
const report={passed:reports.every(r=>r.maxRootErrorM<1e-8&&r.maxPositionErrorM<1e-8&&r.maxRotationErrorDeg<.0001&&r.footStateMismatchFrames===0),note:'Measures live causal solver versus accepted offline staircase planner with identical prescribed root and NN input. This is separate from embedded offline algorithm parity.',reports};
fs.writeFileSync(path.join(folder,'live-stairs-parity.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));if(!report.passed)process.exitCode=1;
