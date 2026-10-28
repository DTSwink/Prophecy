/* Recorded real Run-policy turn; no server, inference or user-state writes. */
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),H=require('./handoff.js'),{load}=require('./test-bank.cjs');
const fixture=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'data/descent-turn-fixture.json.gz'))));
const rig=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'))),run=K.decode(fixture.data,rig.parents);
const started=performance.now(),m=K.prepare(run,fixture.settings),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const left=run.names.indexOf('foot_l'),at=m.sample(53/60),old=fixture.before[106].feet[0];
const lowered=old.p[1]-at.pose.points[left][1];
check('Reported foot loses over25cm of surplus height',lowered>.25);
check('Reported shoe clears the tread by less than5cm',at.feet[0].soleGap>0&&at.feet[0].soleGap<.05);
check('Reported ankle is below its hip instead of raised above it',at.pose.points[S.leg(at.pose,run.names,'L').hip][1]-at.pose.points[left][1]>.20);
let contactError=0,pinRotation=0,contactsRetained=0,flatError=0,peakRotationBefore=0,peakRotationAfter=0,peakKickBefore=0,peakKickAfter=0;
const handoffPlan=H.requestFor(m,run);
for(let i=0;i<m.frames.length;i++)for(let side=0;side<2;side++){
 const f=m.frames[i],before=fixture.before[i].feet[side],l=S.leg(f.raw,run.names,side?'R':'L'),foot=f.feet[side];
 if(foot.contact){
  contactError=Math.max(contactError,distance(R.add(f.pose.points[l.foot],R.rotate(f.pose.q[l.foot],foot.contact.localPoint)),foot.contact.point));
  if(before.contact){
   contactsRetained++;
   contactError=Math.max(contactError,distance(f.pose.points[l.foot],before.p));
   pinRotation=Math.max(pinRotation,angle(f.pose.q[l.foot],before.q));
  }
 }
 if(!f.influence)flatError=Math.max(flatError,distance(f.pose.points[l.foot],f.raw.points[l.foot]));
 if(i>0&&i<handoffPlan.index){
  peakRotationBefore=Math.max(peakRotationBefore,angle(before.q,fixture.before[i-1].feet[side].q));
  peakRotationAfter=Math.max(peakRotationAfter,angle(f.pose.q[l.foot],m.frames[i-1].pose.q[l.foot]));
  if(i>1){
   const kick=(a,b,c)=>R.length(R.sub(R.sub(a,b),R.sub(b,c)))*m.fps;
   peakKickBefore=Math.max(peakKickBefore,kick(before.p,fixture.before[i-1].feet[side].p,fixture.before[i-2].feet[side].p));
   peakKickAfter=Math.max(peakKickAfter,kick(f.pose.points[l.foot],m.frames[i-1].pose.points[l.foot],m.frames[i-2].pose.points[l.foot]));
  }
 }
}
// Acquisition waits for reach, and a descending upper-tread contact now also
// releases before losing the NN's downward leg posture. Its old duration is
// therefore not a valid reference; retained contacts must stay physically exact.
check('Both legs retain supported stance intervals',contactsRetained>0&&m.metrics.pins.every(n=>n>=6));
check('Retained toe/heel material pins and rotations remain exact',contactError<1e-8&&pinRotation<1e-5);
check('Full descent stays clear and within leg reach',m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-5);
check('Flat approach and exit retain exact NN poses',flatError===0);
// One millimetre/second tolerance excludes insignificant fit roundoff.
check('Removing the high foot does not add an angular or velocity snap',peakRotationAfter<20&&peakRotationAfter<peakRotationBefore&&peakKickAfter<=peakKickBefore+.001);
check('Actual NN handoff retains its original root location',distance(handoffPlan.request.roots[1],fixture.beforeHandoff.request.roots[1])<1e-9);
const close=(a,b)=>{if(typeof a==='number')return Math.abs(a-b)<1e-9;if(Array.isArray(a))return a.length===b.length&&a.every((x,i)=>close(x,b[i]));return Object.keys(a).every(k=>close(a[k],b[k]));};
check('Recorded continuation uses the new corrected current/history poses',close(handoffPlan.request.seeds,fixture.afterHandoff.request.seeds));
const full=H.apply(m,run,handoffPlan,fixture.afterHandoff.response);
check('Whole actual continuation remains finite',full.frames.every(f=>f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite)));
check('Handoff does not increase existing NN shoe penetration',full.handoff.maxPenetration<=fixture.beforeHandoff.summary.maxPenetration+1e-6);
const seek=JSON.stringify(full.sample(.9));full.sample(4);full.sample(.2);check('Backward seeks remain deterministic',JSON.stringify(full.sample(.9))===seek);
for(const gait of ['walk','run']){
 const bank=load(gait,.49);
 const down=K.prepare(bank,{...K.defaults,gait,terrain:'down',phase:.49,clearance:1});
 check(gait+' descent retains collision and reach',down.metrics.maxPenetration<1e-5&&down.metrics.maxReachError<1e-5);
 for(const terrain of ['stairs','flat','uneven']){
  const model=K.prepare(bank,{...K.defaults,gait,terrain,phase:.49,clearance:1});
  const hash=crypto.createHash('sha256').update(JSON.stringify(model.frames)).digest('hex');
  check(gait+' '+terrain+' is byte-identical to before',hash===fixture.unchangedHashes[gait+'-'+terrain]);
 }
}
const result={passed:true,checks,currentFrame:53,loweredCm:lowered*100,shoeGapCm:{before:old.gap*100,after:at.feet[0].soleGap*100},peakRotationBefore,peakRotationAfter,peakKickBefore,peakKickAfter,contactError,metrics:m.metrics,handoff:full.handoff,elapsedMs:performance.now()-started};
fs.writeFileSync(path.join(__dirname,'snapshots/descent-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
