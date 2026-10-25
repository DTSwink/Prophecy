import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump);
const base=read('miss-investigation.json').settings,checks=[],measurements=[];
const check=(name,v)=>{assert(v,name);checks.push(name);};
for(const [gait,phase,cone] of [['run',.3,60],['walk',.67,30]]){
 const raw=await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait,duration:1,phase,drawn:true})})).json(),run=F.decodeNN(raw);
 for(const jumpBlend of [0,.2,.8]){
  const s={...base,mode:gait==='walk'?'walk':'jump',runPhase:phase,supportCone:cone,jumpBlend},f=F.create(run,jumps,s,m.parents);
  const tag=`${gait} phase ${phase} blend ${jumpBlend}`,start=Math.max(f.abortTime,f.edge/f.speed);
  check(tag+' misses without launch',Number.isFinite(f.abortTime)&&!Number.isFinite(f.jumpStart));
  const first=f.sample(start),offset=R.sub(first.pose.points[1],first.root);let previous=first,maxUp=0,maxOffset=0;
  for(let i=1;i<=480;i++){
   const frame=f.sample(start+i/240);
   maxUp=Math.max(maxUp,frame.pose.points[1][1]-previous.pose.points[1][1]);
   maxOffset=Math.max(maxOffset,R.length(R.sub(R.sub(frame.pose.points[1],frame.root),offset)));
   assert(frame.root[1]<=previous.root[1]+1e-9&&frame.vy<=0,tag+' root must only fall');previous=frame;
  }
  check(tag+' pelvis never bounces upward',maxUp<1e-9);
  check(tag+' pelvis follows root trajectory',maxOffset<1e-9);
  const a=f.sample(start-1e-7).pose,b=f.sample(start+1e-7).pose;
  check(tag+' pelvis continuous at edge',R.length(R.sub(a.points[1],b.points[1]))<1e-5);
  const aa=R.localize(f.sample(start+.25).pose.points,f.sample(start+.25).pose.q,m.parents),bb=R.localize(f.sample(start+.4).pose.points,f.sample(start+.4).pose.q,m.parents),arm=m.names.indexOf('upperarm_l');
  check(tag+' limb animation continues',R.length(R.qlog(R.qm(aa.q[arm],R.qinv(bb.q[arm]))))>1e-4);
  const saved=JSON.stringify(f.sample(start+.15));f.sample(4);f.sample(0);
  check(tag+' seek deterministic',saved===JSON.stringify(f.sample(start+.15)));
  measurements.push({gait,phase,jumpBlend,abortTime:f.abortTime,fallStart:start,maxPelvisUpPerTick:maxUp,maxRootLocalPelvisError:maxOffset});
 }
}
fs.writeFileSync(new URL('abort-pelvis-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
