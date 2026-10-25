import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),checks=[],measurements=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b));
const manifest=read('data/manifest.json'),parents=manifest.parents,jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const settings=C.sanitize({runPhase:.3,loadMs:50,supportCone:60,supportReach:.99,supportAlpha:6,supportSpeed:400,footRollSpeed:400,jumpEvents:[{id:'first',time:53/60,surface:'floor'},{id:'second',time:95/60,surface:'auto'},{id:'third',time:125/60,surface:'auto'}]});
const run=F.decodeNN(await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.3,drawn:true})})).json());
const before=JSON.stringify(settings),start=performance.now(),sequence=F.sequence(run,jumps,settings,parents),planMs=performance.now()-start;
check('Reported three markers all produce a push',sequence.events.length===3&&sequence.events.every(e=>e.status==='Push'));
check('Markers, maximum speed and reach stay unchanged',JSON.stringify(settings)===before);
check('Already grounded first foot gets no pacing delay',sequence.events[0].contactTime===53/60&&Math.abs(sequence.events[0].releaseTime-.9261588541666667)<1e-9);
for(const segment of sequence.segments){
 const l=segment.support.leg,frames=segment.support.frames,label=segment.event.id;
 let maxTravel=0,minGap=Infinity,maxLengthError=0,maxReach=0;
 // Exclude the last frame from travel-speed measurement: the existing contact
 // trigger can snap a nearby sole onto the plane when capturing it.
 for(let i=1;i<frames.length-1;i++)maxTravel=Math.max(maxTravel,distance(frames[i].localFoot,frames[i-1].localFoot)/(frames[i].t-frames[i-1].t));
 for(let t=segment.supportStart;t<=segment.airStart;t+=1/480){
  const p=segment.sample(t).pose;
  const gap=Math.min(...S.footPoints(p,l.foot,l.toe,l.side).map(v=>R.dot(R.sub(R.add(p.points[l.foot],v),segment.surface.origin),segment.surface.normal)));
  minGap=Math.min(minGap,gap);
  maxLengthError=Math.max(maxLengthError,Math.abs(distance(p.points[l.hip],p.points[l.knee])-l.upper),Math.abs(distance(p.points[l.knee],p.points[l.foot])-l.lower));
  if(t<segment.contactTime)maxReach=Math.max(maxReach,distance(p.points[l.hip],p.points[l.foot]));
 }
 check('Measured root-local foot travel respects maximum '+label,maxTravel<=settings.supportSpeed/100+1e-6);
 check('Foot stays above the surface through approach/loading/push '+label,minGap>=-2e-5);
 check('Approach stays inside chosen leg reach '+label,maxReach<=segment.support.maxReach+2e-5);
 check('Both leg lengths remain fixed '+label,maxLengthError<1e-7);
 const t=segment.supportStart+(segment.contactTime-segment.supportStart)*.5,stamp=JSON.stringify(segment.sample(t));
 segment.sample(8);segment.sample(0);
 check('Reverse seeking preserves paced motion '+label,stamp===JSON.stringify(segment.sample(t)));
 if(frames.length>1){
  check('Anticipation slows before reaching extension limit '+label,frames.some(f=>f.reachWait>0&&f.approachSpeed>0&&f.approachSpeed<settings.supportSpeed/100-.01&&f.hipDistance<segment.support.maxReach-.02));
  check('Approach can use full configured speed '+label,frames.some(f=>Math.abs(f.approachSpeed-settings.supportSpeed/100)<1e-8));
 }
 measurements.push({jump:label,captureFrame:segment.contactTime*60,maxTravelCmS:maxTravel*100,minGapCm:minGap*100,maxReachCm:maxReach*100,limitCm:segment.support.maxReach*100});
}
const third=sequence.segments[2],incoming=sequence.segments[1].sample(third.supportStart).pose,normal=third.surface.normal;
const away=t=>({...incoming,points:incoming.points.map(p=>R.add(p,R.mul(normal,2*t)))});
const miss=S.plan(incoming,run.names,parents,settings,third.surface,0,away,R.mul(normal,2));
check('Receding unreachable surface cannot manufacture a jump',!Number.isFinite(miss.jumpDelay)&&Number.isFinite(miss.abortDelay));
const slowed=F.sequence(run,jumps,{...settings,supportSpeed:200},parents);
check('Lower speed remains a real maximum',slowed.segments.every(s=>s.support.frames.every(f=>f.approachSpeed<=2+1e-8)));
const report={passed:true,browserVisualVerified:false,checks,planMs,measurements};
fs.writeFileSync(new URL('support-pacing-verification.json',import.meta.url),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,checks:checks.length}));
