'use strict';
// Independent unbundled canonical generator captures the actual material
// support sequence. The native root adapter must replay it without foot IK/NN.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),surfacePath=path.resolve(__dirname,'../../Labs/FootIKLab/surface.js');
const records=[],forecasts=[],commands=[];let parameters;
const wire=value=>JSON.parse(JSON.stringify(value));
global.__captureRoot=(motion,params)=>{
 parameters=params;
 return {...motion,finish(context,supports){const receipt=motion.finish(context,supports);records.push({time:context.time,root:context.base.slice(),context:{time:context.time,position:context.base,velocity:context.velocity,normal:context.normal,bodyRotation:context.rootQ,bodyUp:context.bodyUp,gaitRotation:context.surfaceQ,mass:context.mass,pinNormal:context.pinNormal,surface:context.nextSurface.id,courseSurface:context.courseSurface.id,hasFloor:context.hasFloor,useEdited:context.useEdited,...(context.slide?{slide:context.slide}:{})},supports:supports.map(x=>({surface:x.surface.id,point:x.point.slice(),normal:x.normal.slice()})),receipt:structuredClone(receipt)});return receipt;},forecast(context,supports,ticks){const result=motion.forecast(context,supports,ticks);forecasts.push({tick:Math.round(context.time*120),ticks,supports:supports.map(x=>({surface:x.surface.id,point:x.point.slice(),normal:x.normal.slice()})),positions:result.map(x=>x.base)});return result;}};
};
global.__capturePose=command=>commands.push({pose:command.pose,stance:command.stance,untilPlant:command.untilPlant});
const moduleValue=new Module(surfacePath,module);moduleValue.filename=surfacePath;moduleValue.paths=Module._nodeModulePaths(path.dirname(surfacePath));
const source=fs.readFileSync(surfacePath,'utf8'),needle='const motion=createRootMotion({s,terrain,height,speed,gravity,enabled,metrics,events});';
assert.equal(source.split(needle).length,2);
moduleValue._compile(source.replace(needle,'const motion=global.__captureRoot(createRootMotion({s,terrain,height,speed,gravity,enabled,metrics,events}),{s,height,speed,gravity,enabled,duration});').replace('const p=command?.pose||raw?.[i]||rawAt(i);','const p=command?.pose||raw?.[i]||rawAt(i);global.__capturePose(command);'),surfacePath);require.cache[surfacePath]=moduleValue;
const K=require('../../Labs/FootIKLab/footik.js'),C=require('../../Labs/FootIKLab/surface-coupling.js');
async function main(){
 const input=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,'current-yaw-stop10.expected.json'))),run=K.decode(input.source,input.parents),start=performance.now(),cpu=process.cpuUsage();
 const session=C.createSession(run,input.settings,(_,i)=>input.policySteps[i]);await session.extend(input.endTime);session.close();
 assert.equal(records.length,expected.frames.length);
 // Final FK can round the visual root by one ULP. Physical receipts must
 // match the frozen whole-app oracle exactly; replay uses captured base roots.
 let poseRootRoundingM=0;
 for(let i=0;i<records.length;i++){poseRootRoundingM=Math.max(poseRootRoundingM,Math.hypot(...records[i].root.map((v,j)=>v-expected.frames[i].root[j])));assert.deepEqual(wire(records[i].receipt),expected.frames[i].surface);}
 assert(poseRootRoundingM<1e-12);
 fs.writeFileSync(path.join(directory,'root-support-capture.json'),JSON.stringify({parameters,records,forecasts,commands}));
 global.__footikNN=()=>{throw Error('Root adapter may not call the NN');};vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
 const command=value=>JSON.parse(global.FootIKNative.command(JSON.stringify(value))),extent=Math.max(28,parameters.speed*parameters.duration+.5*Math.abs(parameters.gravity)*parameters.duration**2+2*parameters.height);
 let status=command({op:'rootInit',canonicalTerrain:true,settings:parameters.s,height:parameters.height,speed:parameters.speed,gravity:parameters.gravity,extent});
 for(let i=0;i<records.length;i++){
  assert.deepEqual(status.root.position,wire(records[i].root),'root tick'+i);
  for(const f of forecasts.filter(x=>x.tick===i)){
   const before=JSON.stringify(command({op:'rootStatus'}).snapshot),predicted=command({op:'rootForecast',ticks:f.ticks,supports:f.supports});
   assert.deepEqual(predicted.frames.map(x=>x.position),wire(f.positions),'forecast tick'+i);
   assert.equal(JSON.stringify(command({op:'rootStatus'}).snapshot),before,'forecast changed current root');
  }
  status=command({op:'rootStep',ticks:1,supports:records[i].supports});assert.deepEqual(status.receipts[0],wire(records[i].receipt),'receipt tick'+i);
 }
 command({op:'rootClose'});assert.equal(command({op:'rootStatus'}).enabled,false);
 const wall={id:'wall',origin:[0,0,0],normal:[0,0,-1],tangent:[1,0,0],bounds:[-5,5,-50,50],thickness:.2};
 status=command({op:'rootInit',height:.9,speed:2,settings:{enabled:true,inclineGravity:true,minGravityIncline:80,fullGravity:0,slideEnabled:false},root:{position:[0,1,0],normal:[0,0,-1],velocity:[0,0,0]},surfaces:[wall],travelVelocity:[0,0,2]});
 const result=command({op:'rootStep',ticks:1,supports:[{surface:'wall',point:[0,1,0]}]});assert(result.receipts[0].drive[1]>0,'toward-wall drive was projected to zero');
 command({op:'rootClose'});
 const used=process.cpuUsage(cpu),report={passed:true,frames:records.length,forecasts:forecasts.length,rootErrorM:0,receiptError:0,forecastErrorM:0,canonicalVisualRootRoundingM:poseRootRoundingM,forecastNoMutation:true,towardWallVerticalDrive:result.receipts[0].drive[1],noNNCalls:true,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-start};
 fs.writeFileSync(path.join(directory,'root-runtime.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
