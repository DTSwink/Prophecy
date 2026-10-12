const fs=require('node:fs'),path=require('node:path');
const R=require('../../Labs/SwordHolsterLab/recovery.js'),H=require('../../Labs/SwordHolsterLab/holster.js');
const dir=process.argv[2]||'Saved/Diagnostics/SwordPort20261012/controlled';
for(const file of fs.readdirSync(dir).filter(n=>n.endsWith('.json')&&n!=='matrix.json')){
 const d=JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'));if(!d.rows?.length)continue;
 const entry=d.rows.find(r=>r.tick===(d.manual_started||25))||d.rows[0],q=v=>v.slice(3),relative=v=>R.qm(R.qinv(q(v.root)),q(v.target.pelvis));
 const actors={};for(const name of Object.keys(entry.actors)){
  const a=entry.actors[name],changes=[];let previous=-2,maxTargetStep=0,maxPhysicalStep=0;
  for(const row of d.rows){const v=row.actors[name],phase=v.fields.phase;if(phase!==previous){changes.push([row.tick,phase]);previous=phase;}}
  for(let i=1;i<d.rows.length;i++){const a=d.rows[i-1].actors[name],b=d.rows[i].actors[name];if(b.fields.phase>=0&&b.fields.phase!==3){maxTargetStep=Math.max(maxTargetStep,H.angle(q(a.target.head),q(b.target.head)));maxPhysicalStep=Math.max(maxPhysicalStep,H.angle(q(a.physical.head),q(b.physical.head)));}}
  const last=d.rows.at(-1).actors[name];actors[name]={changes,last:last.fields,maxTargetHeadStep:maxTargetStep,maxPhysicalHeadStep:maxPhysicalStep,
   actorTurn:H.angle(q(a.root),q(last.root)),pelvisTurn:H.angle(q(a.target.pelvis),q(last.target.pelvis)),relativePelvisTurn:H.angle(relative(a),relative(last))};
 }
 console.log(JSON.stringify({file,reason:d.reason,actors},null,2));
}
