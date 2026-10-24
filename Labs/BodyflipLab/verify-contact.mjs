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
const results=[],check=(v,msg)=>assert(v,msg);
const cases=[{file:'contact-check.json',settings:read('state.json').settings}];
for(const gait of ['run','walk'])for(const drawn of [false,true])for(const foot of ['L','R'])
 cases.push({file:gait+'-default'+(drawn?'-drawn':'')+'.json',settings:{...C.defaults,mode:gait==='walk'?'walk':'jump',jumpFoot:foot,jumpEarly:.3}});
for(const test of cases){
 const f=F.create(F.decodeNN(read('data/'+test.file)),jumps,test.settings,m.parents),l=f.support.leg;
 check(Number.isFinite(f.jumpStart),'Expected reachable contact '+test.file+'/'+l.side);
 let maxGap=0,maxDrift=0;
 for(let i=0;i<=60;i++){
  const p=f.sample(f.jumpStart+f.release*i/60).pose;
  const sole=Math.min(...Object.values(ctx.boxes(p,{ankle:l.foot,toe:l.toe})).map(bottom));
  maxGap=Math.max(maxGap,Math.abs(sole));
  maxDrift=Math.max(maxDrift,R.length(R.sub(p.points[l.foot],f.support.terminal.foot)));
 }
 check(maxGap<2e-5,'Rendered sole contacts floor throughout pin');
 check(f.sample(f.jumpStart+f.release/2).supportTarget[1]<2e-5,'Roll contact stays on floor');
 const frames=f.support.frames,maxSpeed=Math.max(...frames.slice(1).map((v,i)=>R.length(R.sub(v.localFoot,frames[i].localFoot))*240));
 check(maxSpeed<=test.settings.supportSpeed/100+1e-6,'No approach teleport or speed excess');
 const a=f.sample(f.jumpStart-1e-7).pose,b=f.sample(f.jumpStart).pose;
 check(Math.max(...a.points.map((v,i)=>R.length(R.sub(v,b.points[i]))))<1e-4,'Continuous takeoff');
 check(f.support.terminal.distance<=test.settings.supportTrigger+1e-7,'Distance gate retained');
 results.push({file:test.file,foot:l.side,jumpStart:f.jumpStart,pinSeconds:f.release,maxGap,maxDrift,maxSpeed});
}
fs.writeFileSync(new URL('contact-verification.json',import.meta.url),JSON.stringify({passed:true,results},null,2));
console.log(JSON.stringify({passed:true,cases:results.length,results}));
