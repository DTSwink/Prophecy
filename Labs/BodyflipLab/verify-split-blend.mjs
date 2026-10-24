import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const m=read('data/manifest.json'),run=F.decodeNN(read('data/roll-check.json'));
const jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump);
const settings={...read('roll-settings.json'),footRollSpeed:400},checks=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
check('Legacy blend migrates to both controls',C.sanitize({jumpBlend:.38}).legBlend===.38);
check('Explicit zero survives migration',C.sanitize({jumpBlend:.38,legBlend:0}).legBlend===0);
check('Separate values persist',C.sanitize(C.sanitize({jumpBlend:.12,legBlend:.6})).legBlend===.6);
for(const matchLeg of [false,true]){
 const make=(body,leg)=>F.create(run,jumps,{...settings,matchLeg,jumpBlend:body,legBlend:leg},m.parents);
 const base=make(.2,.2),body=make(.8,.2),leg=make(.2,.8),zero=make(.2,0),l=base.support.leg;
 const chain=[l.hip,l.knee,l.foot,l.toe],others=m.names.map((_,i)=>i).filter(i=>!chain.includes(i));
 const local=(f,t)=>{const p=f.sample(t).pose;return R.localize(p.points,p.q,m.parents);};
 let bodyChange=0,legChange=0;
 for(const dt of [.01,.1,.3,.7,.85]){
  const t=base.airStart+dt,a=local(base,t),b=local(body,t),c=local(leg,t);
  check(`Match ${matchLeg}: body leaves support joints unchanged at ${dt}`,chain.every(i=>angle(a.q[i],b.q[i])<1e-8));
  check(`Match ${matchLeg}: leg leaves other joints unchanged at ${dt}`,others.every(i=>angle(a.q[i],c.q[i])<1e-8));
  bodyChange=Math.max(bodyChange,...others.map(i=>angle(a.q[i],b.q[i])));
  legChange=Math.max(legChange,...chain.map(i=>angle(a.q[i],c.q[i])));
 }
 check(`Match ${matchLeg}: body duration changes body motion`,bodyChange>.01);
 check(`Match ${matchLeg}: leg duration changes leg motion`,legChange>.01);
 check(`Match ${matchLeg}: zero leg hands off immediately`,zero.sample(zero.airStart+.001).supportState!=='BLEND');
 check(`Match ${matchLeg}: contact and release timing unchanged`,[body,leg,zero].every(f=>f.jumpStart===base.jumpStart&&f.release===base.release));
 check(`Match ${matchLeg}: short leg completes independently`,base.sample(base.airStart+.21).supportState!=='BLEND'&&leg.sample(leg.airStart+.21).supportState==='BLEND');
}
fs.writeFileSync(new URL('split-blend-verification.json',import.meta.url),JSON.stringify({passed:true,checks},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length}));
