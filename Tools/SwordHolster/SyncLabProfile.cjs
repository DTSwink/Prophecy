// Export runtime tuning only. Unreal follows its live NN and physical holster.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),lab=path.join(root,'Labs/SwordHolsterLab');
const H=require(path.join(lab,'holster.js')),B=require(path.join(lab,'bodyreach.js'));
const data=require(path.join(lab,'data/motions.json')),saved=JSON.parse(fs.readFileSync(path.join(lab,'state.json'),'utf8'));
const p=structuredClone(saved.parameters),reference=B.make(data,H.motion(data,'idle',0)).reference;
for(const key of ['holsterRotationStabilization','motion','sheathe','startTick','duration','gazeYaw','holsterX','holsterY','holsterZ','holsterPitch','holsterYaw','holsterRoll'])delete p[key];
p.bodyReference=Object.fromEntries(['spine','right','left'].map((key,i)=>[key,reference[i]]));
if(saved.controls?.bypassCurves)for(const key of ['drawCurve','drawSlideCurve','sheatheCurve','sheatheSlideCurve'])p[key]=require(path.join(lab,'retime.js')).linear();
const output={schema:'sword_holster_runtime_v2',sourceHash:crypto.createHash('sha256').update(JSON.stringify(saved.parameters)).digest('hex'),parameters:p};
const destination=path.join(root,'Content/locomotion/SwordHolsterProfile.json');
fs.writeFileSync(destination,JSON.stringify(output,null,2)+'\n');console.log(destination);
