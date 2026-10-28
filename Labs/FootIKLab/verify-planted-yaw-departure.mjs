import fs from 'node:fs';
import path from 'node:path';
import Module,{createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),S=require('./support.js');
const file=path.resolve('Labs/FootIKLab/footik.js'),original=fs.readFileSync(file,'utf8');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),rig=read('data/rig.json'),data=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json');
const skip='if(Math.abs(plan.contacts[a]?.yaw||0)>1e-6||Math.abs(plan.contacts[b]?.yaw||0)>1e-6)continue;';
const variants={
 current:original,
 noPinYaw:original.replace('let turn=[0,0,0,1],shift=[0,0,0],total=0;','return sample=>sample; let turn=[0,0,0,1],shift=[0,0,0],total=0;'),
 arcOn:original.replace(skip,'const turned=false;'),
 forwardOnly:original.replace(skip,'const turned=Math.abs(plan.contacts[a]?.yaw||0)>1e-6||Math.abs(plan.contacts[b]?.yaw||0)>1e-6;').replace('p[2]=from[2]+(to[2]-from[2])*e;p[1]=from[1]+(to[1]-from[1])*e;','p[2]=from[2]+(to[2]-from[2])*e;if(!turned)p[1]=from[1]+(to[1]-from[1])*e;').replace('p[1]+=arc*h;','if(!turned)p[1]+=arc*h;'),
 slowInitial:original.replaceAll('+2*(i-a)/fps','+1*(i-a)/fps'),
 linearHeight:original.replace('if(!turned)p[1]=from[1]+(to[1]-from[1])*e;','p[1]=from[1]+(to[1]-from[1])*e;'),
 turnCorridor:original.replace(/if\(run\.direction&&run\.direction!=='forward'\)\{(\r?\n\s*\/\/ Lateral smoothing)/,"if(settings.rootYawSpeed||(run.direction&&run.direction!=='forward')){$1"),
};
for(const margin of [.02,.03,.04])variants['margin'+Math.round(margin*1000)]=original.replace('[[0,0],[.006,0],[-.006,0],[0,.006],[0,-.006]]',`[[0,0],[${margin},0],[-${margin},0],[0,${margin}],[0,-${margin}]]`);
for(const lead of [2,4,6,8])variants['lead'+lead]=original.replace('  const swings=[];',`  for(let end=0;end<count;end++){
   const c=contacts[end];if(!c||contacts[end+1]?.stanceId===c.stanceId||Math.abs(c.yaw||0)<1e-6)continue;
   let next=end+1;while(next<count&&!contacts[next])next++;
   if(next>=count||targets[next][1]<=targets[end][1]+.005||targets[next][2]<=targets[end][2]+.05)continue;
   let first=end;while(first>0&&contacts[first-1]?.stanceId===c.stanceId)first--;
   const start=Math.max(first+Math.ceil(fps*.12),end-${lead}+1);
   for(let j=start;j<=end;j++){states[j]='SWING';contacts[j]=null;targets[j]=undefined;limits[j]=undefined;rotations[j]={footQ:legs[j][side].footQ,toeQ:legs[j][side].toeQ};offsets[j]=geometry(raw[j],legs[j][side]);}
  }
  const swings=[];`);
const selected=process.argv[2]||'current';
let source=variants[selected];if(!source)throw Error(selected);
if(selected!=='current'&&source===original)throw Error('Requested VM replacement did not match: '+selected);
source=source.replace('return {frames,terrain,settings,metrics','return {debug:{plans,planned,base,legs,swingRotations},frames,terrain,settings,metrics');
const mod=new Module(file);mod.filename=file;mod.paths=Module._nodeModulePaths(path.dirname(file));mod._compile(source,file);
const K=mod.exports,run=K.decode(data,rig.parents),m=K.prepare(run,settings),deg=180/Math.PI;
const point=(f,s,raw=false)=>{const p=raw?f.raw:f.pose,l=S.leg(p,run.names,s?'R':'L');return p.points[l.foot];};
const local=(f,s,raw=false)=>{const p=raw?f.raw:f.pose,l=S.leg(p,run.names,s?'R':'L');return R.rotate(R.qinv(p.q[l.pelvis]),R.sub(p.points[l.foot],p.points[l.pelvis]));};
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*deg;
const rows=m.frames.map((f,i)=>{
 const p=point(f,1),raw=point(f,1,true),prev=m.frames[Math.max(0,i-1)],v=R.mul(R.sub(p,point(prev,1)),120),nv=R.mul(R.sub(raw,point(prev,1,true)),120);
 const l=m.debug.legs[i][1],shape=S.footPoints(f.pose,l.foot,l.toe,'R'),initial=m.debug.plans[1].offsets[i];
 return {frame:i/2,state:f.feet[1].state,position:p,raw,velocity:v,nnVelocity:nv,local:local(f,1),nnLocal:local(f,1,true),contact:f.feet[1].contact?.stanceId||null,floor:m.terrain.floorFor(p,shape),planFloor:m.terrain.floorFor(p,initial),shoeZ:shape.map(o=>o[2]+p[2]).reduce((a,x)=>[Math.min(a[0],x),Math.max(a[1],x)],[Infinity,-Infinity]),plan:m.debug.plans[1].targets[i]};
});
const ranges=[[68,82],[69,82],[72,82],[82,90],[68,100]],intervals=ranges.map(([a,b])=>{
 const begin=rows[a*2],end=rows[b*2],d=R.sub(end.position,begin.position),nd=R.sub(end.raw,begin.raw),inside=rows.slice(a*2+1,b*2+1);
 return {a,b,displacement:d,nnDisplacement:nd,pelvisLocalDelta:R.sub(end.local,begin.local),nnPelvisLocalDelta:R.sub(end.nnLocal,begin.nnLocal),meanCourseSpeed:d[2]/((b-a)/60),minCourseSpeed:Math.min(...inside.map(r=>r.velocity[2])),maxUpSpeed:Math.max(...inside.map(r=>r.velocity[1])),maxCourseSpeed:Math.max(...inside.map(r=>r.velocity[2]))};
});
let maxFootStep=0,maxBoneStep=0,maxFootAccel=0;
for(let i=2;i<m.frames.length;i++)for(let s=0;s<2;s++){
 const f=m.frames[i],p=m.frames[i-1],pp=m.frames[i-2],l=S.leg(f.pose,run.names,s?'R':'L');
 maxFootStep=Math.max(maxFootStep,angle(f.pose.q[l.foot],p.pose.q[l.foot]));
 for(const bone of[l.hip,l.knee])maxBoneStep=Math.max(maxBoneStep,angle(f.pose.q[bone],p.pose.q[bone]));
 const accel=R.mul(R.add(R.sub(f.pose.points[l.foot],R.mul(p.pose.points[l.foot],2)),pp.pose.points[l.foot]),120*120);maxFootAccel=Math.max(maxFootAccel,R.length(accel));
}
const departures=[];for(let side=0;side<2;side++)for(const span of m.debug.plans[side].swings){const a=Math.max(0,span.start-1),f=m.frames[a],l=m.debug.legs[a][side],c=f.feet[side].contact;if(!c)continue;const shoe=S.footFrame(f.pose,l.foot,l.toe,l.side),b=Math.min(a+24,span.end),speeds=Array.from({length:b-a},(_,j)=>R.mul(R.sub(point(m.frames[a+j+1],side),point(m.frames[a+j],side)),120));departures.push({side:l.side,release:a/2,pitch:Math.atan2(shoe.forward[1],shoe.up[1])*deg,yaw:c.yaw,soleGap:f.feet[side].soleGap,earlyUpPeak:Math.max(...speeds.map(s=>s[1])),earlyForwardMean:speeds.reduce((v,s)=>v+s[2],0)/speeds.length});}
const result={variant:selected,metrics:m.metrics,intervals,maxFootStep,maxBoneStep,maxFootAccel,departures,swings:m.debug.plans.map(p=>p.swings.map(s=>({start:s.start/2,end:s.end/2}))),rows};
fs.writeFileSync(new URL('snapshots/yaw-knee-departure-'+selected+'.json',import.meta.url),JSON.stringify(result,null,2));
console.log(JSON.stringify({...result,rows:rows.filter(r=>[67,68,69,70,72,74,76,78,80,82,84,86,88,90,95,100].includes(r.frame))},null,2));
