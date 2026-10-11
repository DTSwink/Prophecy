// Frozen lab oracle for the native port; never writes the live lab state.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),lab=path.join(root,'Labs/SwordHolsterLab'),out=path.join(root,'Saved/Diagnostics/SwordLabSync20261011');
const H=require(path.join(lab,'holster.js')),Head=require(path.join(lab,'headlook.js')),B=require(path.join(lab,'bodyreach.js')),R=require(path.join(lab,'recovery.js'));
const data=require(path.join(lab,'data/motions.json')),setup=require(path.join(lab,'data/unreal-setup.json')),profile=JSON.parse(fs.readFileSync(path.join(out,'profile.json')));
const rows=[];
for(const motion of ['idle','walk'])for(const gaze of [0,170,-170])for(const exponent of [1,2.7])for(const tilt of [0,30,45,70,90]){
 const ctx=Head.make(data),base0=H.motion(data,motion,0,gaze),body=B.make(data,base0),frames=[];let state=null;
 for(let tick=0;tick<=300;tick++){
  const time=tick/60,base=H.motion(data,motion,time),gazed=H.motion(data,motion,time,gaze),v=[Math.sin(tick*.013)*2.4,.15*Math.sin(tick*.017),.2];
  const pose=B.apply(body,gazed,v),holster=H.compose(setup.holster,gazed[data.names.indexOf('pelvis')]),full=H.compose(setup.seated,holster),target=H.point(full,setup.baseBladeLocal);
  const options={tick,startTick:0,lookOutTick:90,maxLookIn:180,maxLookOut:240,lookAtAlpha:.7,lookInExponent:exponent,lookOutExponent:exponent,lookInSpeedAlpha:.3,handArrivalTick:75,neckBase:base,gazeNeckBase:gazed,lookOutQ:gazed[ctx.head].q};
  const f=Head.step(ctx,pose,base,target,state,{...options,maxDownAngle:tilt});state=f.state;
  frames.push({base:gazed,pose,target,q:state.q,neck:ctx.chain.map(j=>f.pose[j]),done:f.info.done});
 }
 rows.push({motion,gaze,exponent,tilt,frames});
}
const geometry=[];
for(const alpha of [0,.1,.45,1]){
 const model=H.prepare(data,setup,{...profile,slideRotationCorrection:alpha});
 for(let tick=model.plan.endTick;tick<=model.plan.slideEnd;tick+=.25){const t=tick/60,f=H.sampleBody(model,t),p=(tick-model.plan.endTick)/(model.plan.slideEnd-model.plan.endTick);geometry.push({alpha,full:H.compose(setup.seated,f.holster),entry:model.sheathEntry,insertion:f.insertion,time:p,scale:f.scale,goal:f.goal});}
}
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'channels.json'),JSON.stringify({names:data.names,parents:data.parents,setup:{...setup,swordMesh:undefined,holsterMesh:undefined,tip:H.bladeTip(setup)},rows,geometry}));console.log({headCases:rows.length,geometrySamples:geometry.length});
