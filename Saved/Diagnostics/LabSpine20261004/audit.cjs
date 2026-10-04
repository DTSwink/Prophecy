const fs=require('fs'),path=require('path');
const lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab';
const R=require(path.join(lab,'recovery.js'));
const s=JSON.parse(fs.readFileSync(path.join(lab,'snapshots/snapshot_0006.json')));
const manifest=JSON.parse(fs.readFileSync(path.join(lab,'data/manifest.json')));
const clip=manifest.clips.find(c=>c.name===s.attack),meta=clip.variants.find(v=>v.id===s.variant);
const bytes=fs.readFileSync(path.join(lab,meta.file));
const model=R.prepare(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents);
const opt={enabled:s.controls.enabled,duration:+s.controls.duration,inertia:+s.controls.inertia,returnEasing:s.attackReturnEasing[s.attack],spineTurn:+s.controls.spineTurn,boneInertia:s.attackBoneInertia[s.attack]};
const sample=(t,o=opt)=>R.sample(model,t,o);
const pose=R.anchor(model,sample(s.time),meta.target);
const flatten=x=>x.flat(Infinity);
const error=(a,b)=>Math.max(...flatten(a).map((v,i)=>Math.abs(v-flatten(b)[i])));
const angle=(a,b)=>R.length(R.qlog(R.qm(R.qinv(a),b)))*180/Math.PI;
const local=p=>R.localize(p.points,p.q,manifest.parents);
const names=['pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','head','hand_r'];
const end=model.attackSeconds,rows=[];
for(const frame of [-2,-1,0,1,2,3,4,5,6,8,10,12,15,16]){
 const a=sample(end+(frame-1)/60),b=sample(end+frame/60),la=local(a),lb=local(b);
 const row={frame,elapsed:frame/60};
 for(const name of names){const j=manifest.names.indexOf(name);row[name]={world_deg:angle(a.q[j],b.q[j]),parent_deg:angle(la.q[j],lb.q[j])};}
 rows.push(row);
}
const seam={};
for(const epsilon of [1e-6,1/60]){
 const a=sample(end-epsilon),b=sample(end),c=sample(end+epsilon),la=local(a),lb=local(b),lc=local(c);
 seam[epsilon]={};
 for(const name of names){const j=manifest.names.indexOf(name);seam[epsilon][name]={beforeWorldDegSec:angle(a.q[j],b.q[j])/epsilon,afterWorldDegSec:angle(b.q[j],c.q[j])/epsilon,beforeLocalDegSec:angle(la.q[j],lb.q[j])/epsilon,afterLocalDegSec:angle(lb.q[j],lc.q[j])/epsilon};}
}
const report={snapshot:'snapshot_0006',attack:s.attack,variant:s.variant,snapshotTime:s.time,attackEnd:end,options:opt,posePointError:error(pose.points,s.displayedPose.points),poseAxesError:error(pose.axes,s.displayedPose.axes),rows,seam};
// Calculation only: with the pelvis frozen, spine_01 must retain its incoming
// global angular velocity expressed in the bone frame, including parent motion.
const turned=model.turnCache.model,j=model.spine,prev=turned.poses.at(-2),last=turned.poses.at(-1);
const carried={...turned,turnCache:null,velocity:turned.velocity.slice()};
carried.velocity[j]=R.mul(R.qlog(R.qm(R.qinv(prev.q[j]),last.q[j])),meta.fps);
report.counterfactual=[];
for(const easing of [opt.returnEasing,1])for(const carry of [false,true]){
 const candidate=carry?carried:turned,settings={...opt,spineTurn:0,returnEasing:easing},epsilon=1e-6;
 const start=R.sample(candidate,end,settings),after=R.sample(candidate,end+epsilon,settings);
 const next=R.sample(candidate,end+1/60,settings);
 report.counterfactual.push({easing,carry,spine1InitialDegSec:angle(start.q[j],after.q[j])/epsilon,
  spine1FirstTickDeg:angle(start.q[j],next.q[j]),spine5FirstTickDeg:angle(start.q[manifest.names.indexOf('spine_05')],next.q[manifest.names.indexOf('spine_05')]),
  pelvisUnchanged:error(after.q[manifest.names.indexOf('pelvis')],last.q[manifest.names.indexOf('pelvis')])});
}
fs.writeFileSync(path.join(__dirname,'audit.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({...report,rows:undefined},null,2));
console.log('frame pelvisWorld spine1World spine1Local spine5World spine5Local');
for(const r of rows)console.log(r.frame,...[r.pelvis.world_deg,r.spine_01.world_deg,r.spine_01.parent_deg,r.spine_05.world_deg,r.spine_05.parent_deg].map(x=>x.toFixed(4)));
