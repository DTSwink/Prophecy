// Inspect the captured guides without changing the lab or Unreal.
const fs=require('node:fs'),R=require('../../Labs/SwordHolsterLab/recovery.js'),H=require('../../Labs/SwordHolsterLab/holster.js'),FK=require('../../Labs/SwordHolsterLab/armfk.js'),P=require('../../Labs/SwordHolsterLab/elbowpole.js');
const d=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const names=['clavicle_r','upperarm_r','lowerarm_r','hand_r','spine_05'],parents=[-1,0,1,2,-1],arm=[1,2,3],pose=v=>({p:v.slice(0,3),q:v.slice(3)});
for(const name of Object.keys(d.rows[0].actors))for(let i=1;i<d.rows.length;i++){
 const prev=d.rows[i-1].actors[name],v=d.rows[i].actors[name];
 if(!prev.authored||!v.authored||v.fields.phase!==2||prev.fields.phase!==2||prev.fields.slide_progress!==0)continue;
 const a=prev.authored,b=v.authored,before=names.map(n=>pose(a.bodyPose[n])),after=names.map(n=>pose(b.bodyPose[n]));
 const seed=a.heldArm.map(pose);
 const source=FK.apply(before,arm,parents,seed),goal=FK.apply(after,arm,parents,b.guideB.map(pose));
 const basis={d:a.poleDirection,zero:a.poleZero};
 const out={name,tick:d.rows[i].tick,reach:R.length(R.sub(before[3].p,before[1].p)),pole:[a.poleAngle,b.poleAngle],guide:[b.guideTickA,b.guideTickB],bones:[]};
 for(const k of arm)out.bones.push({bone:names[k],actualWorld:H.angle(before[k].q,after[k].q),guideWorld:H.angle(source[k].q,goal[k].q)});
 out.sourceBend=P.measure(source,arm,4,basis);out.actualBend=P.measure(before,arm,4,basis);
 const carried=FK.apply(after,arm,parents,seed),origin=carried[1].p;
 const turn=R.fromTo(R.sub(carried[3].p,origin),R.sub(after[3].p,origin));
 for(const k of arm)carried[k]={...carried[k],p:R.add(origin,R.rotate(turn,R.sub(carried[k].p,origin))),q:R.qm(turn,carried[k].q)};
 H.solve(carried,arm,after[3]);
 const corrected=P.apply(carried,arm,4,b.poleAngle,P.frame(carried,arm,4,basis));
 out.transportedStep=arm.map(k=>[names[k],H.angle(before[k].q,corrected[k].q)]);
 console.log(JSON.stringify(out));
}
