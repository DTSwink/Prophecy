import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump),ref=C.poseFromShared(m),checks=[],measurements=[];
const check=(n,ok)=>{assert(ok,n);checks.push(n);},dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
for(const gait of ['run','walk'])for(const foot of ['L','R'])for(const standRatio of [.5,3]){
 const run=F.decodeNN(read('data/'+gait+'-default-drawn.json')),f=F.create(run,jumps,{...C.defaults,jumpFoot:foot,jumpEarly:.3,standRatio,jumpBlend:.08},m.parents,ref),tag=[gait,foot,standRatio].join('/'),l=f.support.leg,bones=[l.hip,l.knee,l.foot,l.toe],clip=F.trimStart(jumps.find(c=>c.name===f.start));
 check(tag+' takeoff and velocity selection',Number.isFinite(f.jumpStart)&&f.jumpStyle===(standRatio===3?'Stand':'Run'));
 const releasePose=f.sample(f.airStart).pose,launch=R.localize(releasePose.points,releasePose.q,m.parents);
 let best=Infinity;
 for(let i=0;i<=Math.ceil(f.loopStart*clip.fps);i++){
  const source=F.at(clip,Math.min(i/clip.fps,f.loopStart),m.parents),raw=R.localize(source.points,source.q,m.parents),local={p:launch.p.slice(),q:launch.q.slice()};
  for(const bone of bones){local.q[bone]=raw.q[bone];if(bone!==l.hip)local.p[bone]=raw.p[bone];}
  best=Math.min(best,dist(R.fk(local,m.parents).points[l.foot],releasePose.points[l.foot]));
 }
 check(tag+' globally closest foot frame',Math.abs(best-f.matchDistance)<1e-8);
 check(tag+' ahead slows and behind speeds up',Math.abs(f.matchTime-f.release)<1e-8?Math.abs(f.legRate-1)<1e-8:f.matchTime>f.release?f.legRate<1:f.legRate>1);
 check(tag+' synchronized finish',Math.abs(f.legTime(f.loopStart-1e-8)-f.loopStart)<1e-6);
 const time=(f.release+.08+f.loopStart)/2,p=f.sample(f.jumpStart+time).pose,source=F.at(clip,f.legTime(time),m.parents),local=R.localize(p.points,p.q,m.parents),raw=R.localize(source.points,source.q,m.parents);
 check(tag+' plays actual retimed leg frames',bones.every(i=>angle(local.q[i],raw.q[i])<1e-6));
 const ordinary=F.at(clip,time,m.parents),other=R.localize(ordinary.points,ordinary.q,m.parents),otherLeg=m.names.map((_,i)=>i).filter(i=>i>1&&!bones.includes(i));
 check(tag+' rest of body keeps normal clock',otherLeg.every(i=>angle(local.q[i],other.q[i])<1e-6));
 const ghost=f.animationLeg(f.jumpStart+time,p);check(tag+' ghost shows retimed target',ghost.points.every((v,k)=>dist(v,p.points[bones[k]])<1e-8));
 for(const boundary of [f.airStart,f.jumpStart+f.loopStart]){
  const a=f.sample(boundary-1e-7).pose,b=f.sample(boundary+1e-7).pose;
  check(tag+' continuous boundary '+boundary,Math.max(...a.points.map((v,i)=>dist(v,b.points[i])))<1e-4);
 }
 const repeat=JSON.stringify(f.sample(f.airStart+.1));f.sample(20);f.sample(0);check(tag+' arbitrary seeks deterministic',JSON.stringify(f.sample(f.airStart+.1))===repeat);
 measurements.push({gait,foot,standRatio,release:f.release,match:f.matchTime,rate:f.legRate,gap:f.matchDistance});
}
fs.writeFileSync(new URL('match-leg-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
