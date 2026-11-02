'use strict';
// Recorded NN inputs only. This inventory never starts an inference worker or
// reads/writes the live viewer state. Source recordings stay outside the port.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const root=path.resolve(__dirname,'../..');
function read(relative){const bytes=fs.readFileSync(path.join(root,relative));return JSON.parse(relative.endsWith('.gz')?zlib.gunzipSync(bytes):bytes);}
function cases(){
 const out=[],descent='Labs/FootIKLab/data/descent-pelvis-fixture.json.gz',record=read(descent);
 for(const item of record.cases){
  const base={...item.settings,rootYawSpeed:0,slideEnabled:false,deleteFloorFrame:-1};
  for(const terrain of ['flat','stairs','down','uneven'])out.push({name:`${item.gait}-${terrain}`,tags:[item.gait,terrain,'full-NN-source'],dependency:descent,input:{op:'prepare',source:item.data,settings:{...base,terrain}}});
  for(const approach of ['toward','parallel'])for(const slopeAngle of [0,45,90])out.push({name:`${item.gait}-surface-${approach}-${slopeAngle}`,tags:[item.gait,'surface',approach,`${slopeAngle}deg`],dependency:descent,input:{op:'prepare',source:item.data,settings:{...base,terrain:'incline',approach,slopeAngle,pelvisCloser:20,inclineGravity:true,minGravityIncline:80,fullGravity:70}}});
 }
 const captured=[
  ['current-yaw-stop10','Saved/FootIKArmSmooth20261029/yaw10-fixture.json.gz'],
  ['current-yaw-stop12','Saved/FootIKArmWall20261029/fixture.json.gz'],
  ['coupled-wall-run','Labs/FootIKLab/data/wall-frame-run-fixture.json.gz'],
  ['coupled-wall-walk','Labs/FootIKLab/data/wall-frame-walk-fixture.json.gz'],
  ...['final-run-forward','run-backward','final-run-left','run-right','walk-forward','final-walk-backward','walk-left','walk-right','final-run-forward-yaw-120','final-run-forward-yaw120','run-backward-yaw-120','run-backward-yaw120','walk-forward-82','run-backward-85','parallel-run-forward','parallel-walk-backward','parallel-turn','floor-deletes-during-entry'].map(n=>[n,`Saved/FootIKSlideAudit20261029/${n}.fixture.json.gz`])
 ];
 for(const [name,dependency] of captured){
  const compact=`Tools/FootIK/parity-fixtures/${name}.json.gz`;
  let input,available=dependency;
  if(fs.existsSync(path.join(root,compact))){input=read(compact);available=compact;}
  else{const f=read(dependency);input={op:'prepare',source:f.request.source,settings:f.request.settings,policySteps:f.response.steps,endTime:f.request.endTime??5};}
  const s=input.settings;
  out.push({name,tags:['coupled',s.gait,s.direction,s.approach,`${s.slopeAngle}deg`,...(s.slideEnabled?['slide']:[])],dependency:available,originalDependency:dependency,input});
 }
 for(const gait of ['run','walk'])for(const terrain of ['stairs','down','uneven']){
  const name=`app-${gait}-${terrain}`,dependency=`Tools/FootIK/parity-fixtures/${name}.json.gz`;
  if(fs.existsSync(path.join(root,dependency)))out.push({name,tags:['whole-app',gait,terrain,'nn-handoff'],dependency,input:read(dependency)});
 }
 return out;
}
module.exports={root,read,cases};
