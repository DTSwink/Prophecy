import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json'),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const fixture=read('data/cone-choice-case.json'),settings=C.sanitize(fixture.settings),pose={...fixture.pose,axes:fixture.pose.q.map(R.toAxes)},surface=S.platformSurface(fixture.surface);
const distance=(a,b)=>R.length(R.sub(a,b)),c=S.candidates(pose,fixture.names,settings,surface,fixture.velocity);
check('Reported pose has closer theoretical left target',c.scores[0].idealDistance<c.scores[1].idealDistance);
check('Cone reverses ranking and selects right foot',c.selected===1&&c.scores[1].distance<c.scores[0].distance);
check('Reported post-cone distances reproduced',Math.abs(c.scores[0].distance-.315277371)<1e-6&&Math.abs(c.scores[1].distance-.035315161)<1e-6);
for(const [i,l] of c.legs.entries()){
 const score=c.scores[i],planted={points:[],axes:[]};planted.points[l.foot]=[0,0,0];planted.points[l.toe]=R.rotate(l.plant.footQ,l.toeLocal);planted.axes[l.foot]=R.toAxes(l.plant.footQ);planted.axes[l.toe]=R.toAxes(l.plant.toeQ);
 const ankle=R.sub(score.cone.contact,S.lowestOffset(planted,l,surface.normal));
 check('Same ankle metric after cone '+l.side,Math.abs(score.distance-distance(pose.points[l.foot],ankle))<1e-10);
 check('Both feet eligible in reported case '+l.side,score.eligible);
 const plan=S.plan(pose,fixture.names,fixture.parents,{...settings,jumpFoot:l.side},surface,0,null,fixture.velocity);
 check('Compared target agrees with planner cone '+l.side,distance(score.constrainedSurface,plan.frames[0].cone.contact)<1e-8);
 check('Explicit foot choice retained '+l.side,plan.leg.side===l.side);
}
const chosen=S.plan(pose,fixture.names,fixture.parents,settings,surface,0,null,fixture.velocity);
check('Reported right foot captures immediately',chosen.leg.side==='R'&&chosen.jumpDelay===0);
for(const angle of [0,30,60,85]){
 const candidate=S.candidates(pose,fixture.names,{...settings,supportCone:angle},surface,fixture.velocity),eligible=candidate.scores.filter(s=>s.eligible);
 check('Nearest constrained target wins at cone angle '+angle,candidate.scores[candidate.selected].distance===Math.min(...eligible.map(s=>s.distance)));
}
for(const depth of [.001,.0095,.05,.5,2]){
 const ground=S.ground(2),cone=S.coneTarget([0,-depth,0],[0,0,0],ground,60);
 check('No penetration cutoff at depth '+depth,cone.valid&&Math.abs(cone.gap-depth)<1e-9);
 check('Finite platform still required '+depth,!S.coneTarget([3,-depth,0],[3,0,0],ground,60).valid);
}
const distant=S.rectangle('distant',[0,-50,0],[1,0,0],[0,0,1],[-100,100,-100,100]),far=S.candidates(pose,fixture.names,settings,distant,fixture.velocity);
check('Wide cone can intersect far slab',far.scores.some(s=>s.cone.valid));
check('Unreachable slab remains excluded',far.scores.every(s=>!s.inRange&&!s.eligible));
const raw=await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:settings.runPhase,drawn:true})})).json(),run=F.decodeNN(raw),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const before=JSON.stringify(settings),sequence=F.sequence(run,jumps,settings,m.parents),first=sequence.segments[0];
check('New rule also selects closer constrained first foot',first.supportFoot==='L'&&first.supportScores[0].distance<first.supportScores[1].distance);
check('First grounded foot captures at original marker',first.contactTime===settings.jumpEvents[0].time);
check('Settings and markers are untouched',JSON.stringify(settings)===before);
check('Later markers honestly miss after changed first launch',sequence.events.slice(1).every(e=>e.status==='Miss'&&e.reason==='No ground in cone')&&sequence.segments.slice(1).every(s=>!s.bounce&&s.pushDebug(s.supportStart)===null));
check('Surface ranking and planned foot agree',sequence.segments.every(s=>s.surfaceChoices.find(r=>r.surface===s.surface.id).foot===s.supportFoot));
const platforms=sequence.surfaces.map(S.platformRecord),reordered=F.sequence(run,jumps,{...settings,platforms:platforms.slice().reverse()},m.parents);
check('Platform order cannot change eligible pair',reordered.segments.every((s,i)=>!sequence.segments[i].surfaceChoices.some(r=>r.eligible)||(s.surface.id===sequence.segments[i].surface.id&&s.supportFoot===sequence.segments[i].supportFoot)));
// If no surface is available, equally distant fallback labels may tie. Neither
// order may turn that diagnostic fallback into a launch or change root motion.
check('Unavailable surface tie cannot alter misses or trajectory',reordered.events.every((e,i)=>e.status===sequence.events[i].status)&&distance(reordered.sample(3).root,sequence.sample(3).root)<1e-8);
const withFar=F.sequence(run,jumps,{...settings,platforms:[S.platformRecord(distant),...platforms]},m.parents);
check('Unreachable slab cannot steal surface choice',withFar.events.every((e,i)=>e.surfaceId===sequence.events[i].surfaceId));
check('No platforms cannot manufacture a push',F.sequence(run,jumps,{...settings,platforms:[]},m.parents).events.every(e=>e.status==='Miss'));
const report={passed:true,browserVisualVerified:false,checks,reportedDistances:c.scores.map(s=>({foot:s.foot,ideal:s.idealDistance,afterCone:s.distance})),events:sequence.events};fs.writeFileSync(new URL('surface-choice-verification.json',import.meta.url),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,checks:checks.length}));
