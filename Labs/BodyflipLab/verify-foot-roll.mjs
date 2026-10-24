import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump);
const ctx=vm.createContext({...R,normalize:R.unit,norm:R.length,posAt:(p,i)=>p.points[i],axisAt:(p,i,a)=>p.axes[i][a]});
vm.runInContext(fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8')+';globalThis.boxes=WebGLMotionRenderer.prototype.footBoxes;',ctx);
const bottom=b=>b.center[1]-(Math.abs(b.forward[1])*b.dims[0]+Math.abs(b.side[1])*b.dims[1]+Math.abs(b.up[1])*b.dims[2])/2;
const dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),checks=[],measurements=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const cases=[{label:'Saved',data:read('data/roll-check.json'),settings:read('roll-settings.json')}];
for(const gait of ['run','walk'])for(const foot of ['L','R'])for(const plantPitch of [-10,0,10,20])
 cases.push({label:gait+'/'+foot+'/'+plantPitch,data:read('data/'+gait+'-default-drawn.json'),settings:{...C.defaults,mode:gait==='walk'?'walk':'jump',jumpFoot:foot,jumpEarly:.3,plantPitch}});
for(const footRollSpeed of [0,180,360,1440])cases.push({label:'Speed '+footRollSpeed,data:read('data/roll-check.json'),settings:{...read('roll-settings.json'),footRollSpeed}});
for(const c of cases){
 const settings=C.sanitize(c.settings),f=F.create(F.decodeNN(c.data),jumps,settings,m.parents),l=f.support.leg;
 check(c.label+' reaches contact',Number.isFinite(f.jumpStart));
 const boxes=p=>ctx.boxes(p,{ankle:l.foot,toe:l.toe}),pitch=p=>Math.asin(boxes(p).foot.forward[1])*180/Math.PI;
 const start=f.sample(f.supportStart).pose,land=f.sample(f.jumpStart).pose,end=f.sample(f.airStart).pose;
 check(c.label+' target landing pitch',Math.abs(pitch(land)+settings.plantPitch)<1e-5);
 const forward=boxes(land).foot.forward;
 check(c.label+' faces root forward',Math.abs(forward[0])<1e-7&&forward[2]>0);
 const middle=f.sample((f.supportStart+f.jumpStart)/2).pose;
 check(c.label+' rotates during approach',angle(middle.q[l.foot],land.q[l.foot])<angle(start.q[l.foot],land.q[l.foot])+1e-8);
 let maxSoleGap=0,maxContactError=0,minApproachSole=Infinity,priorPitch=pitch(land),monotone=true;
 for(let i=0;i<=80;i++){
  const p=f.sample(f.supportStart+(f.jumpStart-f.supportStart)*i/80).pose;
  minApproachSole=Math.min(minApproachSole,...Object.values(boxes(p)).map(bottom));
  const frame=f.sample(f.jumpStart+f.release*i/80),b=boxes(frame.pose);
  maxSoleGap=Math.max(maxSoleGap,Math.abs(Math.min(...Object.values(b).map(bottom))));
  maxContactError=Math.max(maxContactError,Math.abs(frame.supportTarget[1]),Math.max(0,frame.supportTarget[2]-f.edge));
  const a=pitch(frame.pose);monotone&&=a<=priorPitch+1e-5;priorPitch=a;
 }
 const probe=Math.min(f.release*.4,.01),expected=Math.min(Math.max(0,settings.toeOffPitch-settings.plantPitch),settings.footRollSpeed*probe);
 check(c.label+' exact configurable angular speed',Math.abs(pitch(land)-pitch(f.sample(f.jumpStart+probe).pose)-expected)<1e-5);
 check(c.label+' rolls toward toe-off',monotone&&pitch(end)<=pitch(land)+1e-6);
 check(c.label+' sole stays grounded while rolling',maxSoleGap<2e-5);
 check(c.label+' contact stays on available ground',maxContactError<2e-5);
 check(c.label+' no new approach penetration',minApproachSole>=Math.min(0,...Object.values(boxes(start)).map(bottom))-.002);
 for(const t of [f.supportStart,f.jumpStart,f.airStart,f.airStart+settings.jumpBlend]){
  const a=f.sample(t-1e-7).pose,b=f.sample(t+1e-7).pose;
  check(c.label+' continuous handoff '+t,Math.max(...a.points.map((v,i)=>dist(v,b.points[i])))<1e-4&&angle(a.q[l.foot],b.q[l.foot])<1e-4);
 }
 const saved=JSON.stringify(f.sample(f.jumpStart+f.release/2));f.sample(20);f.sample(0);
 check(c.label+' seeks deterministic',saved===JSON.stringify(f.sample(f.jumpStart+f.release/2)));
 measurements.push({label:c.label,jump:f.jumpStart,push:f.release,startPitch:pitch(start),plantPitch:pitch(land),endPitch:pitch(end),maxSoleGap,maxContactError,minApproachSole,ankleTravel:dist(land.points[l.foot],end.points[l.foot])});
}
const receipt={passed:true,checks,measurements};fs.writeFileSync(new URL('foot-roll-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
