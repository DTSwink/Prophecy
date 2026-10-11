// Compact real-Unreal neck regression; no images or live-state writes.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),file=process.argv[2]||'Saved/Diagnostics/SwordOvernight20261011/detail/sim-walk-high-detail.json';
const data=JSON.parse(fs.readFileSync(path.join(root,file))),names=['spine_05','neck_01','neck_02','head'];
const pose=p=>names.map(n=>({p:p[n].slice(0,3),q:p[n].slice(3)}));
const cases=Object.keys(data.rows[0].actors).map(name=>({name,frames:data.rows.map(row=>{
 const v=row.actors[name],a=v.authored;
 return {tick:row.tick,active:!!a,pose:pose(a?a.bodyPose:v.target),base:pose(a?a.base:v.target),q:v.target.head.slice(3),delta:a?.headDelta,phase:v.fields.phase,slide:v.fields.slide_progress,gaze:v.gaze};
})}));
fs.writeFileSync(path.join(root,'Labs/SwordHolsterLab/data/head-handoff-regression.json'),JSON.stringify({names,parents:[-1,0,1,2],cases}));
