'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),input=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.input.json')));
let held=null,calls=0;global.__footikNN=text=>{calls++;const r=JSON.parse(text);held=r.seeds?.[1]||held;return JSON.stringify({pose:held});};
vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
const R=require('../../Labs/FootIKLab/recovery.js'),K=require('../../Labs/FootIKLab/footik.js'),command=x=>JSON.parse(global.FootIKNative.command(JSON.stringify(x)));
const settings={...input.settings,inclineGravity:true,minGravityIncline:80,slideEnabled:true,slideSpeed:0,fullGravity:100},wall={id:'real-wall',origin:[0,0,0],normal:[0,0,-1],tangent:[1,0,0],bounds:[-100,100,-100,100]};
const start=command({op:'rootInit',settings,height:.9,surfaces:[wall],root:{position:[0,2,0],velocity:[0,-1,0],normal:[0,0,-1],bodyRotation:R.fromTo([0,1,0],[0,0,-1]),surface:wall.id},travelVelocity:[0,0,2]});
assert(start.root.slide,'wall starts in slide');command({op:'rootStep',ticks:2,supports:[]});
const dropped=command({op:'rootForecast',ticks:32,surfaces:[],rootSurfaces:[],surfaceRevision:2,supports:[]});
assert.equal(dropped.frames[0].slide,undefined,'removed wall releases slide');
for(let i=1;i<=32;i++){const r=command({op:'rootStep',ticks:1,supports:[]});assert.deepEqual(r.root.position,dropped.frames[i].position,'void forecast matches actual root');assert.deepEqual(r.root.mass,dropped.frames[i].mass);assert.equal(r.receipt.contacts,0);}
const before=command({op:'rootStatus'}),result=command({op:'rootStep',ticks:120,supports:[]});assert(result.root.mass[1]<0,'no invisible floor');assert.deepEqual(result.receipt.collisionCorrection,[0,0,0]);assert(Math.abs(result.root.velocity[1]-before.root.velocity[1]+9.81)<1e-12,'gravity remains active');command({op:'rootClose'});
const run=K.decode(input.source,input.parents);command({op:'init',source:input.source,parents:input.parents,initialPair:{previous:run.poses[0],current:run.poses[1]},settings,root:{position:[0,2,0],velocity:[0,0,0],normal:[0,1,0]},travelVelocity:[0,0,0],surfaces:[],rootSurfaces:[]});
let frames=0;for(let i=0;i<20;i++){const r=command({op:'tick',ticks:1});assert.equal(r.supports.length,0);assert.equal(r.frame.surface.contacts,0);assert(r.frame.feet.every(f=>!f.contact&&!f.slideContact));assert(r.frame.pose.points.flat().every(Number.isFinite));frames++;}command({op:'close'});
const report={passed:true,removedWallEndsSlide:true,phantomContacts:0,voidForecastFramesExact:32,freefallAcceleration:9.81,emptySurfacePoseFrames:frames,policyCalls:calls};fs.writeFileSync(path.join(directory,'live-void.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
