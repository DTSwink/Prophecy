import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),S=require('./support.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),reference=C.poseFromShared(m),jumps=read('data/jumps.json').clips.map(F.decodeJump);
const checks=[],measurements=[],check=(name,ok)=>{assert(ok,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b));
check('Requested defaults and kinematic retained',C.defaults.supportReach===.99&&C.defaults.supportTrigger===.05&&C.defaults.supportAlpha===1&&C.defaults.supportSpeed===800&&C.defaults.motion==='kinematic');
const safe=C.sanitize({supportReach:9,supportTrigger:-1,supportAlpha:NaN,supportSpeed:0});
check('Control limits reject invalid divisions and ranges',safe.supportReach===1&&safe.supportTrigger===0&&safe.supportAlpha===1&&safe.supportSpeed===.1);
for(const cache of ['run-default.json','run-default-drawn.json']){
 const run=F.decodeNN(read('data/'+cache));
 const make=extra=>F.create(run,jumps,{...C.defaults,matchLeg:false,jumpEarly:0,supportAlpha:0,...extra},m.parents,reference);
 for(const foot of ['Auto','L','R']){
  const f=make({jumpFoot:foot}),l=f.support.leg,label=cache+' '+foot;
  check(label+' chooses corresponding ground target',foot==='Auto'?f.supportFoot===f.supportScores.reduce((a,b)=>a.distance<=b.distance?a:b).foot:f.supportFoot===foot);
  check(label+' keeps trimmed matching jump variant',f.sourceStart===1/3&&f.start.endsWith(f.supportFoot+'foot'));
  check(label+' waits for contact within the gate',f.jumpStart>1&&f.support.terminal.distance<=.05);
  check(label+' root stays level throughout approach',f.sample((1+f.jumpStart)/2).root[1]===f.sample(1).root[1]);
  check(label+' root rises after gate',f.sample(f.jumpStart+1/240).root[1]>f.sample(f.jumpStart).root[1]);
  let drift=0,reach=0,lengthError=0;
  for(let t=0;t<=f.release;t+=1/1000){
   const p=f.sample(f.jumpStart+t).pose;
   drift=Math.max(drift,distance(p.points[l.foot],f.support.terminal.foot));
   reach=Math.max(reach,distance(p.points[l.foot],p.points[l.hip]));
   lengthError=Math.max(lengthError,Math.abs(distance(p.points[l.hip],p.points[l.knee])-l.upper),Math.abs(distance(p.points[l.knee],p.points[l.foot])-l.lower));
  }
  check(label+' planted ankle stays fixed in world space',drift<2e-5);
  check(label+' pin does not exceed 99 percent reach',reach<=f.support.maxReach+2e-5);
  check(label+' two bone IK preserves segment lengths',lengthError<2e-5);
  const releasePose=f.sample(f.airStart).pose,next=f.sample(f.airStart+1e-7).pose;
  check(label+' release is position continuous',Math.max(...releasePose.points.map((p,i)=>distance(p,next.points[i])))<1e-4);
  const after=f.release+C.defaults.jumpBlend+.05,p=f.sample(f.jumpStart+after).pose,source=F.at(F.trimStart(jumps[f.supportFoot==='L'?0:1]),after,m.parents),pl=R.localize(p.points,p.q,m.parents),sl=R.localize(source.points,source.q,m.parents);
  check(label+' support leg returns to authored local jump rotations',[l.hip,l.knee,l.foot,l.toe].every(i=>R.length(R.qlog(R.qm(pl.q[i],R.qinv(sl.q[i]))))<1e-6));
  const expected=JSON.stringify(f.sample(f.jumpStart+.05));f.sample(8);f.sample(0);
  check(label+' arbitrary seeks and repeats reproduce the plant',JSON.stringify(f.sample(f.jumpStart+.05))===expected);
  check(label+' finite capped void fall',f.sample(20).vy===-20&&f.sample(20).pose.points.flat().every(Number.isFinite));
  measurements.push({cache,foot:f.supportFoot,jumpStart:f.jumpStart,pinSeconds:f.release,drift,reach,lengthError});
 }
 const normal=make({jumpEarly:0}),early=make({jumpEarly:.1});
 check(cache+' early default is one tenth second',C.defaults.jumpEarly===.1);
 check(cache+' earlier support uses cached run at 0.9 s',Math.abs(early.supportStart-.9)<1e-10&&early.jumpStart<normal.jumpStart);
 check(cache+' early jump keeps original ledge',early.edge===normal.edge&&Math.abs(early.edge-(normal.speed-.12))<1e-9);
 check(cache+' alpha never moves the ledge',make({jumpEarly:.1,supportAlpha:20}).edge===early.edge);
 check(cache+' early takeoff still obeys foot gate',early.support.terminal.distance<=C.defaults.supportTrigger);
 check(cache+' 800 cm/s respects per-step approach speed',early.support.frames.length>1&&Math.max(...early.support.frames.slice(1).map((f,i)=>distance(f.localFoot,early.support.frames[i].localFoot)*240))<=8+1e-7);
 check(cache+' early root stays grounded before support trigger',Math.abs(early.sample(early.supportStart).root[1]-early.sample(early.jumpStart).root[1])<1e-9);
 check(cache+' early root rises at its new trigger',early.sample(early.jumpStart+1/240).root[1]>early.sample(early.jumpStart).root[1]);
 check(cache+' early cannot consume entire run',Math.abs(C.sanitize({runSeconds:.1,jumpEarly:5}).jumpEarly-(.1-1/60))<1e-10);
 const slow=make({jumpEarly:.1,supportSpeed:100}),strict=make({jumpEarly:.1,supportSpeed:300,supportTrigger:0});
 check(cache+' slower foot and tighter gate cannot advance jump',slow.jumpStart>early.jumpStart&&strict.jumpStart>=make({jumpEarly:.1,supportSpeed:300}).jumpStart);
 check(cache+' zero gate reaches target before jump',strict.support.terminal.distance<1e-8);
 for(const speed of [100,800,2000]){
  const f=make({jumpEarly:.1,supportSpeed:speed}),frames=f.support.frames;
  const maxSpeed=Math.max(...frames.slice(1).map((v,i)=>distance(v.localFoot,frames[i].localFoot)*240));
  check(cache+' foot speed bound '+speed,maxSpeed<=speed/100+1e-7);
  check(cache+' no jump before gate '+speed,!Number.isFinite(f.jumpStart)||(frames.at(-1).distance<=.05&&frames.at(-1).reachable));
 }
 const blocked=make({supportReach:.5});
 check(cache+' unreachable surface never triggers jump',blocked.jumpStart===Infinity&&blocked.sample(10).phase==='ABORT - FALL'&&blocked.sample(10).pose.points.flat().every(Number.isFinite));
 const moving=make({jumpEarly:.1,supportSpeed:300}),missed=make({jumpEarly:.1,supportSpeed:10}),history=missed.support.frames;
 check(cache+' current 300 cm/s setting advances while approaching',moving.support.terminal.advance>.06&&Number.isFinite(moving.jumpStart));
 check(cache+' root never holds during failed approach',history.every((v,i)=>!i||v.root[2]>history[i-1].root[2]));
 check(cache+' ideal remains root local and ground validated',history.every(v=>distance(v.surface,S.ground(missed.edge).closest(R.add(v.root,missed.support.idealLocal)))<1e-8));
 check(cache+' distance recorded at every authored substep',history.every((v,i)=>Math.abs(v.t-i/240)<1e-9&&Math.abs(v.distance-distance(v.foot,v.target))<1e-9));
 check(cache+' abort occurs on first increasing distance',history.at(-1).distance>history.at(-2).distance+1e-5&&history.slice(1,-1).every((v,i)=>v.distance<=history[i].distance+1e-5));
 check(cache+' aborted attempt never launches',missed.jumpStart===Infinity&&missed.failureReason==='Distance growing'&&Number.isFinite(missed.abortTime));
 check(cache+' aborted root keeps forward momentum',missed.sample(missed.abortTime+.2).root[2]>missed.sample(missed.abortTime).root[2]+.99);
 check(cache+' aborted attempt falls with capped speed',missed.sample(20).phase==='ABORT - FALL'&&missed.sample(20).vy===-20&&missed.sample(20).root[1]<missed.sample(missed.abortTime).root[1]);
 const beforeAbort=missed.sample(missed.abortTime-1e-8),afterAbort=missed.sample(missed.abortTime);
 check(cache+' abort releases without pose snap',Math.max(...beforeAbort.pose.points.map((p,i)=>distance(p,afterAbort.pose.points[i])))<1e-5);
 const failedRepeat=JSON.stringify(missed.sample(1.5));missed.sample(0);missed.sample(20);
 check(cache+' failure replay and seeks are deterministic',JSON.stringify(missed.sample(1.5))===failedRepeat);
 const earlyAbort=make({jumpEarly:.5,supportReach:.5,supportSpeed:10,supportAlpha:80});
 check(cache+' abort before ledge keeps running on ground',earlyAbort.sample(earlyAbort.abortTime).phase==='ABORT - RUN'&&earlyAbort.sample(earlyAbort.abortTime).vy===0);
 check(cache+' aborted run starts falling once off ledge',earlyAbort.sample(1.05).phase==='ABORT - FALL'&&earlyAbort.sample(1.05).vy<0);
 const gait=make({jumpEarly:.1,jumpFoot:'L'}),gaitTime=gait.supportStart+.04,arm=m.names.indexOf('upperarm_r');
 check(cache+' remaining limbs continue cached locomotion during approach',distance(gait.sample(gaitTime).pose.points[arm],R.add(F.at(run,gaitTime,m.parents).points[arm],R.sub(gait.sample(gaitTime).root,F.at(run,gaitTime,m.parents).points[0])))<1e-7);
 measurements.push({cache,foot:moving.supportFoot,jumpStart:moving.jumpStart,approachAdvance:moving.support.terminal.advance,missedAbort:missed.abortTime,recordedTicks:history.length,previousGap:history.at(-2).distance,abortGap:history.at(-1).distance});
 const noLead=make({supportAlpha:0}),lead=make({supportAlpha:2});
 check(cache+' alpha zero removes prediction',noLead.supportScores.every(s=>R.length(s.shift)===0));
 check(cache+' prediction uses root speed times alpha divided by 200',lead.supportScores.every(s=>distance(s.shift,[0,0,lead.speed*2/200])<1e-10));
 check(cache+' ground queries clamp to actual ledge',lead.supportScores.every(s=>s.surface[1]===0&&s.surface[2]<=lead.edge&&Math.abs(s.surface[0])<=1.8));
 const end=F.at(run,1,m.parents),legs=['L','R'].map(s=>S.leg(end,run.names,s)),surface=S.ground(100);
 const targets=S.ideal(end,legs,surface,0,C.defaults),center=surface.closest(end.points[1]),width=distance(end.points[legs[0].hip],end.points[legs[1].hip]);
 check(cache+' ideal feet sit half a hip width each side',targets.every(s=>Math.abs(distance(s.surface,center)-width/2)<1e-10)&&distance(R.mul(R.add(targets[0].surface,targets[1].surface),.5),center)<1e-10);
 for(const alpha of [0,.1,.5,1,20]){
  const points=S.ideal(end,legs,surface,5,{...C.defaults,matchLeg:false,supportAlpha:alpha});
  check(cache+' scaled alpha '+alpha,points.every(s=>distance(s.shift,[0,0,5*alpha/200])<1e-10));
 }
 const tune={...C.defaults,matchLeg:false,supportAlpha:4},rootLead=S.ideal(end,legs,surface,5,tune);
 check(cache+' alpha 4 at 5 m/s gives 10 cm lead',rootLead.every(s=>distance(s.shift,[0,0,.1])<1e-10));
 const spread={...end,points:end.points.map((p,i)=>legs.some(l=>l.foot===i)?R.add(p,[.4,0,0]):p)};
 const changed=S.ideal(spread,legs,surface,5,{...tune,supportSpeed:10});
 check(cache+' foot distance and approach speed cannot change lead',changed.every((s,i)=>distance(s.shift,rootLead[i].shift)<1e-10));
 const turned={...end,q:end.q.map((q,i)=>i===0?R.qexp([0,Math.PI/2,0]):q)};
 check(cache+' lead follows local root heading',S.ideal(turned,legs,surface,5,tune).every(s=>distance(s.shift,[.1,0,0])<1e-10));
 check(cache+' lead scales only with root speed and alpha',S.ideal(end,legs,surface,2.5,tune).every(s=>distance(s.shift,[0,0,.05])<1e-10));
}
const report={passed:true,checks,measurements};fs.writeFileSync(new URL('support-verification.json',import.meta.url),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,checks:checks.length,measurements},null,2));
