import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json');
const jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump),checks=[],measurements=[];
const check=(name,v)=>{assert(v,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b));
const surface=S.ground(2),inside=(c,p)=>distance(p,c.center)<=c.radius+1e-7&&distance(surface.closest(p),p)<1e-7;
for(const angle of [0,15,30,60])for(const apex of [[0,1,0],[1.9,.4,1.9],[0,.1,2.5],[1.7,.4,1.8]]){
 const wanted=[-2,0,3],c=S.coneTarget(apex,wanted,surface,angle);
 check(`Valid intersection ${angle}/${apex}`,c.valid===(distance(c.nearest,c.center)<=c.radius+1e-8));
 if(!c.valid)continue;
 check(`Target within cone and ground ${angle}/${apex}`,inside(c,c.contact));
 let best=Infinity;
 for(let i=0;i<=80;i++)for(let k=0;k<=80;k++){const p=[-1.8+3.6*i/80,0,-3+5*k/80];if(inside(c,p))best=Math.min(best,distance(p,wanted));}
 check(`Nearest feasible target ${angle}/${apex}`,distance(c.contact,wanted)<=best+1e-7);
}
check('Cone defaults to 30 degrees',C.sanitize().supportCone===30);
const settings={...read('saved-profile.json').settings,supportCone:30};
{
 const run=F.decodeNN(read('data/roll-check.json'));
 for(const supportCone of [0,30]){
  const f=F.create(run,jumps,{...settings,supportCone,supportTrigger:0},m.parents);
  check(`Zero gate waits for actual contact at ${supportCone} degrees`,Number.isFinite(f.jumpStart)&&f.support.frames.at(-1).cone.gap<1e-7);
 }
}
for(const gait of ['run','walk'])for(const phase of [.54,.67]){
 const raw=await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait,duration:1,phase,drawn:true})})).json();
 const run=F.decodeNN(raw),s={...settings,mode:gait==='run'?'jump':'walk',runPhase:phase};
 const f=F.create(run,jumps,s,m.parents),l=f.support.leg,initial=f.support.frames[0];
 check(`${gait}/${phase} resolves support`,Number.isFinite(f.jumpStart)||Number.isFinite(f.abortTime));
 if(Number.isFinite(f.jumpStart)){
  check(`${gait}/${phase} respects sole gate`,f.support.frames.at(-1).cone.gap<=s.supportTrigger+1e-7);
  check(`${gait}/${phase} valid contact`,f.support.frames.at(-1).cone.valid);
  for(const fraction of [0,.5,1]){
   const frame=f.sample(f.jumpStart+f.release*fraction),p=frame.pose,low=R.add(p.points[l.foot],S.lowestOffset(p,l,[0,1,0]));
   check(`${gait}/${phase} sole grounded during push ${fraction}`,Math.abs(low[1])<2e-5);
   check(`${gait}/${phase} marker on ground ${fraction}`,distance(S.ground(f.edge).closest(frame.supportTarget),frame.supportTarget)<2e-5);
  }
  const before=f.sample(f.supportStart-1e-7).pose,launch=f.sample(f.jumpStart).pose;
  if(gait==='run'&&phase===.54){
   check('Reported grounded phase jumps immediately',f.jumpStart===f.supportStart);
   check('Immediate push retains foot rotation',distance(before.q[l.foot],launch.q[l.foot])<1e-5);
   check('Grounded foot has no forward replant',Math.abs(before.points[l.foot][2]-launch.points[l.foot][2])<1e-5);
  }
  if(gait==='run'&&phase===.67)check('Airborne foot still approaches',f.jumpStart>f.supportStart);
  const stamp=JSON.stringify(f.sample(f.jumpStart+.01));f.sample(3);f.sample(0);
  check(`${gait}/${phase} deterministic seek`,stamp===JSON.stringify(f.sample(f.jumpStart+.01)));
 }
 const p=f.sample(f.supportStart-1e-6).pose,debug=f.coneDebug(f.supportStart-1e-6,p);
 check(`${gait}/${phase} debug originates at actual lowest sole`,distance(debug.apex,R.add(p.points[l.foot],S.lowestOffset(p,l,[0,1,0])))<1e-8);
 check(`${gait}/${phase} debug retires after airborne`,f.coneDebug(10,p)===null);
 const end=F.at(run,.9,m.parents);
 // Deliberately place all candidate contacts past the platform, with no cone overlap.
 const miss=S.plan(end,run.names,m.parents,C.sanitize(s),S.ground(.1),f.speed);
 check(`${gait}/${phase} no launch from void`,miss.abortDelay===0&&!Number.isFinite(miss.jumpDelay)&&miss.failureReason==='No ground in cone');
 measurements.push({gait,phase,jumpStart:f.jumpStart,abortTime:f.abortTime,foot:l.side,initialGap:initial.cone.gap,landingPitch:f.landingPitch});
}
fs.writeFileSync(new URL('cone-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
