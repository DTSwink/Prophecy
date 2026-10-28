/* Actual turning Run/Walk NN sources; no inference or saved-scene writes. */
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),assert=require('node:assert/strict');
const K=require('./footik.js'),H=require('./handoff.js'),R=require('./recovery.js'),S=require('./support.js');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,'data/descent-drag-fixture.json.gz'))));
const rig=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'))),checks=[],results=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const close=(a,b)=>typeof a==='number'?Math.abs(a-b)<1e-9:Array.isArray(a)?a.length===b.length&&a.every((x,i)=>close(x,b[i])):Object.keys(a).every(k=>close(a[k],b[k]));
for(const c of fixture.cases){
 const run=K.decode(c.data,rig.parents),m=K.prepare(run,c.settings),plan=H.requestFor(m,run),end=plan?.index??m.frames.length,label=c.gait+' ';
 let kick=0,ankle=0,knee=0,lag=0,pinError=0,postureExcess=0,flatError=0,rootError=0;
 for(let i=0;i<m.frames.length;i++){
  const a=m.frames[i],b=m.frames[Math.max(0,i-1)],prev=m.frames[Math.max(0,i-2)];rootError=Math.max(rootError,distance(a.root,a.raw.points[0]));
  if(a.influence===0)for(let j=0;j<run.names.length;j++)flatError=Math.max(flatError,distance(a.pose.points[j],a.raw.points[j]));
  for(let side=0;side<2;side++){
   const l=S.leg(a.raw,run.names,side?'R':'L'),foot=a.pose.points[l.foot],hip=a.pose.points[l.hip],contact=a.feet[side].contact;
   if(i>1&&i<end){
    kick=Math.max(kick,distance(R.sub(foot,b.pose.points[l.foot]),R.sub(b.pose.points[l.foot],prev.pose.points[l.foot]))*m.fps);
    ankle=Math.max(ankle,angle(a.pose.q[l.foot],b.pose.q[l.foot]));knee=Math.max(knee,angle(a.pose.q[l.knee],b.pose.q[l.knee]));
    if(!contact)lag=Math.max(lag,a.raw.points[l.foot][2]-foot[2]);
   }
   if(contact){
    pinError=Math.max(pinError,distance(R.add(foot,R.rotate(a.pose.q[l.foot],contact.localPoint)),contact.point));
    if(foot[2]<hip[2]-.15){
     const supportHip=[hip[0],Math.max(hip[1],foot[1]+a.raw.points[l.hip][1]-a.raw.points[l.foot][1]-.02),hip[2]];
     postureExcess=Math.max(postureExcess,distance(foot,supportHip)-l.reach*.995);
    }
   }
  }
 }
 check(label+'retained contacts leave room for the NN downward leg posture',postureExcess<1e-6);
 check(label+'heel/toe pivots remain fixed during support',pinError<1e-8&&m.metrics.pins.every(n=>n>=6));
 check(label+'whole descent respects shoe clearance and leg lengths',m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-5);
 check(label+'does not add a departure velocity kick',kick<=c.before.kick+.001);
 check(label+'does not introduce knee or ankle pops',ankle<=c.before.angle*1.01&&knee<=c.before.knee*1.01);
 check(label+'does not replace recovery with a later foot lag',lag<=c.before.lag+.001);
 check(label+'retains pure NN flat poses and root travel',flatError===0&&rootError===0);
 check(label+'does not restore the excessive pelvis drop',m.metrics.maxPelvis<=c.before.maxPelvis+.001);
 let full=m;
 if(plan){
  check(label+'continuation uses the corrected current/history poses',close(plan.request.seeds,c.handoff.request.seeds)&&close(plan.request.roots,c.handoff.request.roots));
  full=H.apply(m,run,plan,c.handoff.response);
 }else check(label+'does not invent a new NN handoff',c.handoff===null);
 check(label+'entire continuation is finite',full.frames.every(f=>f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite)));
 if(c.gait==='run'){
  const f=m.sample(51/60),l=S.leg(f.raw,run.names,'L'),before=c.beforeFrames[102],foot=f.pose.points[l.foot],hip=f.pose.points[l.hip];
  check('Reported51 foot advances over30cm instead of trailing the old tread',foot[2]-before.p[l.foot][2]>.30);
  check('Reported51 foot is over20cm below its hip rather than level with it',hip[1]-foot[1]>.20);
  check('Reported51 foot has caught the NN travel rather than dragging behind it',foot[2]>=f.raw.points[l.foot][2]);
  let minimum=Infinity;
  for(let i=96;i<=114;i++){
   const a=m.frames[i],b=m.frames[i-1];minimum=Math.min(minimum,(a.pose.points[l.foot][2]-a.pose.points[l.hip][2])-(b.pose.points[l.foot][2]-b.pose.points[l.hip][2]));
  }
  check('Reported swing keeps progressing relative to the pelvis after departure',minimum>0);
 }
 const sample=JSON.stringify(full.sample(.85));full.sample(4.5);full.sample(.1);check(label+'seeking remains deterministic',JSON.stringify(full.sample(.85))===sample);
 results.push({gait:c.gait,kick,ankle,knee,lag,pinError,postureExcess,metrics:m.metrics,handoff:full.handoff??null});
}
const result={passed:true,checks,results};fs.writeFileSync(path.join(__dirname,'snapshots/descent-drag-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
