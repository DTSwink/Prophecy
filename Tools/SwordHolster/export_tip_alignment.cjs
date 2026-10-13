// Read-only oracle export from the accepted lab. Never edits saved settings.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),lab=root+'/Labs/SwordHolsterLab';
const H=require(lab+'/holster'),R=require(lab+'/recovery'),Tip=require(lab+'/tipalign');
const data=require(lab+'/data/motions.json'),setup=require(lab+'/data/unreal-setup.json'),saved=require(lab+'/state.json').parameters;
const rows=[];
for(const motion of ['idle','walk','run'])for(const shrinkPercent of [20,65]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat:true,motion,shrinkPercent,duration:8,leewayPhase:true};
 const m=H.prepare(data,setup,o),d=m.tipAlign,f=m.frames[d.tick],full=H.seatedSword(setup,f.holster);
 rows.push({motion,holster:f.holster,full,blade:f.sword,tip:m.tip,base:setup.baseBladeLocal,mouth:H.point(full,setup.baseBladeLocal),hand:f.pose[m.arm[2]].p,
   scale:d.scale,tick:d.tick,ticks:d.ticks,tolerance:o.sheatheRotationTolerance,reach:m.o.maxAttachedSpeed,rotation:m.o.maxAttachedRotationSpeed,insertion:d.insertion,
   samples:Array.from({length:d.ticks+1},(_,i)=>{const frame=m.frames[Math.min(d.tick+i,m.frames.length-1)],v=Tip.sample(H,setup,m.tip,d,frame.holster,d.tick+i);return {tick:d.tick+i,holster:frame.holster,tip:H.point(v.sword,m.tip),q:v.sword.q};})});
}
const out=root+'/Saved/Diagnostics/TipAlignPort20261013';fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(out+'/tip-oracle.json',JSON.stringify({rows}));console.log(`Exported ${rows.length} accepted-lab tip paths.`);
