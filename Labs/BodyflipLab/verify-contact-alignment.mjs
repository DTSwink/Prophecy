import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),checks=[],measurements=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
const m=read('data/manifest.json'),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const settings=C.sanitize({runPhase:.61,supportCone:60,supportAlpha:6,supportSpeed:400,footRollSpeed:400,jumpEvents:[{id:'first',time:53/60,surface:'floor'},{id:'second',time:115/60,surface:'auto'},{id:'third',time:146/60,surface:'auto'}]});
const run=F.decodeNN(await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.61,drawn:true})})).json());
const start=performance.now(),sequence=F.sequence(run,jumps,settings,m.parents),planMs=performance.now()-start;
// Whole-body matching and carried transition velocity change later arrival poses.
check('Moving matched-body fixture makes two pushes then reports the last miss',sequence.events.slice(0,2).every(e=>e.status==='Push')&&sequence.events[2].status==='Miss');
const fixture=read('data/cone-choice-case.json'),incoming={...fixture.pose,axes:fixture.pose.q.map(R.toAxes)};
const isolated=F.create(run,jumps,fixture.settings,m.parents,incoming,{time:0,surface:S.platformSurface(fixture.surface),poseAt:t=>({...incoming,points:incoming.points.map(p=>R.add(p,R.mul(fixture.velocity,t)))}),velocityAt:()=>fixture.velocity});
check('Frozen reported incline pose selects right and pushes',isolated.supportFoot==='R'&&isolated.contactTime===0&&isolated.bounce.didPush);
const cases=[...sequence.segments.filter(f=>f.bounce?.didPush),isolated];
for(const f of cases){
 const l=f.support.leg,n=f.surface.normal,label=f.surface.id;
 const bank=p=>Math.abs(R.dot(S.footFrame(p,l.foot,l.toe,l.side).side,n));
 const clearance=p=>Math.min(...S.footPoints(p,l.foot,l.toe,l.side).map(v=>R.dot(R.sub(R.add(p.points[l.foot],v),f.surface.origin),n)));
 const captured=f.sample(f.contactTime).pose,released=f.sample(f.airStart).pose;
 check('Contact begins at the captured ankle '+label,dist(captured.points[l.foot],f.support.terminal.foot)<2e-5);
 check('Shoe levels while contact lasts '+label,f.airStart-f.contactTime>=f.contactMotion.alignDuration?bank(released)<1e-6:bank(released)<bank(captured));
 let maxGap=0,maxBoneError=0,maxTargetError=0;
 for(let t=f.contactTime;t<f.airStart;t+=1/720){
  const p=f.sample(t).pose,c=f.contactMotion.sample(t-f.contactTime);
  maxGap=Math.max(maxGap,Math.abs(clearance(p)));
  maxBoneError=Math.max(maxBoneError,Math.abs(dist(p.points[l.hip],p.points[l.knee])-l.upper),Math.abs(dist(p.points[l.knee],p.points[l.foot])-l.lower));
  maxTargetError=Math.max(maxTargetError,dist(p.points[l.foot],c.foot));
 }
 check('Sole stays on surface throughout loading and push '+label,maxGap<2e-5);
 check('Knee segment lengths remain intact '+label,maxBoneError<1e-7);
 check('Spring and displayed IK use the same moving ankle '+label,maxTargetError<2e-5);
 for(const t of [f.jumpStart,f.airStart]){const a=f.sample(t-1e-6).pose,b=f.sample(t+1e-6).pose;
  check('Ankle continuous at phase boundary '+label+'/'+t,dist(a.points[l.foot],b.points[l.foot])<1e-4);
  check('Foot orientation continuous at phase boundary '+label+'/'+t,dist(a.axes[l.foot][2],b.axes[l.foot][2])<1e-4);
 }
 const t=(f.contactTime+f.airStart)/2,a=JSON.stringify(f.contactMotion.sample(t-f.contactTime));
 f.contactMotion.sample(5);f.contactMotion.sample(0);
 check('Reverse seeking does not change contact '+label,JSON.stringify(f.contactMotion.sample(t-f.contactTime))===a);
 const ideals=f.idealDebug(f.supportStart).targets,eligible=f.supportScores.filter(s=>s.eligible);
 check('Both ideal markers report the selection-time comparison '+label,ideals.length===2&&ideals.every(i=>i.distance===f.supportScores.find(s=>s.foot===i.foot).distance));
 check('Chosen foot is closest among eligible own targets '+label,f.supportScores.find(s=>s.foot===f.supportFoot).distance===Math.min(...eligible.map(s=>s.distance)));
 measurements.push({surface:label,foot:l.side,initialBank:bank(captured),releaseBank:bank(released),maxGap,maxBoneError,maxTargetError,load:f.bounce.loadDuration,push:f.release,releaseVelocity:f.bounce.released.v});
}
const third=isolated,l=third.support.leg,n=third.surface.normal;
// Keep a deliberate corner-contact regression independent of which foot the
// earlier jumps select; fixing selection changes the downstream arrival pose.
const terminal={...third.support.terminal},pose={...terminal.pose,points:terminal.pose.points.map(p=>p.slice()),q:terminal.pose.q.map(q=>q.slice()),axes:terminal.pose.axes.slice()};
const forward=S.footFrame(pose,l.foot,l.toe,l.side).forward,bank=R.qexp(R.mul(forward,Math.PI/3));
terminal.rotation={footQ:R.qm(bank,terminal.rotation.footQ),toeQ:R.qm(bank,terminal.rotation.toeQ)};
for(const i of [l.foot,l.toe]){pose.q[i]=i===l.foot?terminal.rotation.footQ:terminal.rotation.toeQ;pose.axes[i]=R.toAxes(pose.q[i]);}
pose.points[l.toe]=R.add(pose.points[l.foot],R.rotate(pose.q[l.foot],l.toeLocal));
terminal.foot=R.sub(terminal.surface,S.lowestOffset(pose,l,n));
pose.points[l.foot]=terminal.foot;pose.points[l.toe]=R.add(terminal.foot,R.rotate(pose.q[l.foot],l.toeLocal));terminal.pose=pose;
check('Corner-contact fixture is heavily banked',Math.abs(R.dot(S.footFrame(pose,l.foot,l.toe,l.side).side,n))>.5);
for(const speed of [0,100,400]){
 const motion=S.contactMotion(terminal,l,third.surface,{...settings,footRollSpeed:speed}),pushStart=Math.max(.08,motion.alignDuration+.01);motion.startPush(pushStart);
 const sample=t=>{const c=motion.sample(t),p={points:[],axes:[]};p.points[l.foot]=c.foot;p.points[l.toe]=R.add(c.foot,R.rotate(c.rotation.footQ,l.toeLocal));p.axes[l.foot]=R.toAxes(c.rotation.footQ);p.axes[l.toe]=R.toAxes(c.rotation.toeQ);return {c,p,frame:S.footFrame(p,l.foot,l.toe,l.side)};};
 const a=sample(pushStart-.005),b=sample(pushStart+.07);
 check('Alignment completes even if heel/toe speed is zero '+speed,Math.abs(R.dot(a.frame.side,n))<1e-7);
 check('Heel/toe rotation preserves tangent side '+speed,Math.abs(R.dot(b.frame.side,n))<1e-7);
 const pitch=x=>-Math.asin(Math.max(-1,Math.min(1,R.dot(x.frame.forward,n))))*180/Math.PI;
 const change=pitch(b)-pitch(a),expected=Math.min(settings.toeOffPitch-pitch(a),.07*speed);
 check('Existing roll speed controls forward pitch after loading '+speed,Math.abs(change-expected)<.01);
}
fs.writeFileSync(new URL('contact-alignment-verification.json',import.meta.url),JSON.stringify({passed:true,checks,planMs,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,planMs,measurements}));
