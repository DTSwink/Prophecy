// Frozen current-lab trajectory oracle. No writes to lab code, state or assets.
// Geometry is supplied tick by tick, so this tests the pose controller, not the
// different editor pivots or physical response. Entry inertia is checked both off and at the saved setting.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),lab=root+'/Labs/SwordHolsterLab';
const H=require(lab+'/holster'),saved=require(lab+'/state.json');
const data=require(lab+'/data/motions.json'),setup=require(lab+'/data/unreal-setup.json');
const p=structuredClone(saved.parameters);
if(saved.controls?.bypassCurves)for(const k of ['drawCurve','drawSlideCurve','sheatheCurve','sheatheSlideCurve'])p[k]=require(lab+'/retime').linear();
const rows=[];
for(const motion of ['idle','walk','run'])for(const sheathe of [false,true])for(const inertia of [false,true]){
 const m=H.prepare(data,setup,{...p,...p[(sheathe?'sheathe':'draw')+'Body'],motion,sheathe,noCheat:true,entryInertia:inertia?p.entryInertia:0,duration:12});
 const start=m.o.startTick;
 rows.push({motion,sheathe,inertia,start,prior:H.motion(data,motion,(start-1)/60,m.o.gazeYaw),entry:H.motion(data,motion,start/60,m.o.gazeYaw),reachTicks:m.plan.reachEndTick-start,
  slideStart:m.plan.endTick-start,slideTicks:m.plan.slideEnd-m.plan.endTick,finish:m.completionTick===null?null:m.completionTick-start,
  frames:m.frames.slice(start).map(f=>({base:H.motion(data,motion,f.tick/60,m.o.gazeYaw),full:H.seatedSword(setup,f.holster),holster:f.holster,pose:f.pose,sword:f.sword,phase:f.phase,scale:f.scale,insertion:f.insertion}))});
}
const out=root+'/Saved/Diagnostics/SwordAcceptedPort20261013';
fs.writeFileSync(out+'/motion-oracle.json',JSON.stringify({names:data.names,parents:data.parents,setup:{grip:setup.grip,assetScale:setup.assetScale,baseBladeLocal:setup.baseBladeLocal,tip:H.bladeTip(setup),bladeLength:setup.bladeLength},rows}));
console.log(rows.map(({motion,sheathe,reachTicks,slideStart,slideTicks,finish})=>({motion,sheathe,reachTicks,slideStart,slideTicks,finish})));
