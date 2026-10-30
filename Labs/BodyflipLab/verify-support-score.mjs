// Real rig, local fixtures only. No live NN, browser or state writes.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const m=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(m),settings=C.sanitize({supportAlpha:0}),checks=[];
const check=(label,value)=>{assert(value,label);checks.push(label);},floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-4,4,-4,4]);
function pose({leadL=.3,leadR=-.3,gapL=.002,gapR=.002}={}){
 const local=R.localize(reference.points,reference.q,m.parents);local.p[m.names.indexOf('pelvis')][1]-=.18;let p=R.fk(local,m.parents);
 for(const [side,lead,gap] of [['L',leadL,gapL],['R',leadR,gapR]]){
  const l=S.leg(p,m.names,side),offset=S.lowestOffset(p,l,floor.normal),target=[p.points[l.hip][0],gap-offset[1],p.points[l.pelvis][2]+lead];
  p=S.solve(p,l,target,m.parents,.99);
 }
 return p;
}
const select=(p,v=[0,0,2],surface=floor,options=settings)=>S.candidates(p,m.names,options,surface,v),side=c=>c.legs[c.selected].side;
const base=pose(),front=select(base);
check('Both feet have valid contact',front.scores.every(s=>s.eligible));
check('Leading foot wins when both are grounded',side(front)==='L');
check('Reversing travel reverses preference',side(select(base,[0,0,-2]))==='R');
check('Raised front foot loses to grounded rear foot',side(select(pose({gapL:.3})))==='R');
check('Grounded front foot wins against raised rear foot',side(select(pose({gapR:.3})))==='L');
check('Small penetration remains eligible',side(select(pose({gapL:-.002})))==='L');
check('Pure normal motion picks nearer contact',side(select(pose({gapL:.06}),[0,-4,0]))==='R');
check('Manual R remains R',side(select(base,[0,0,2],floor,{...settings,jumpFoot:'R'}))==='R');
check('Manual L remains L despite higher contact cost',side(select(pose({gapL:.3}),[0,0,2],floor,{...settings,jumpFoot:'L'}))==='L');
const level=pose({leadL:0,leadR:0});
check('Sideways movement favors the advancing side',side(select(level,[2,0,0]))==='L'&&side(select(level,[-2,0,0]))==='R');
for(let i=0;i<80;i++){
 const e=(i-40)*1e-6,p=pose({gapL:.002+e,gapR:.002-e});
 check('Contact/velocity noise preserves leading foot '+i,side(select(p,[e,e,2+e]))==='L');
 check('Rest has a stable near-tie '+i,side(select(p,[e,e,-e]))==='L');
}
let changed=false;const heightSweep=[];
for(let i=0;i<=30;i++){
 const height=i/100,c=select(pose({gapL:height})),chosen=side(c);
 check('Raising front foot never restores its preference '+i,!changed||chosen==='R');if(chosen==='R')changed=true;
 heightSweep.push({height,chosen});
}
check('Height eventually overcomes forward preference',changed);
for(const [name,axis,angle] of [['yaw',[0,1,0],1.3],['incline',[1,0,0],Math.PI/4],['wall',[1,0,0],Math.PI/2],['ceiling',[1,0,0],Math.PI]]){
 const q=R.qexp(R.mul(axis,angle)),offset=[3,2,-1],p={points:base.points.map(v=>R.add(R.rotate(q,v),offset)),q:base.q.map(v=>R.qm(q,v))};p.axes=p.q.map(R.toAxes);
 const surface=S.rectangle(name,offset,R.rotate(q,[1,0,0]),R.rotate(q,[0,0,1]),[-4,4,-4,4]),c=select(p,R.rotate(q,[0,0,2]),surface);
 check(name+' uses surface tangent, not world forward',side(c)==='L');
 check(name+' preserves contact and score under rigid transform',c.scores.every((s,i)=>Math.abs(s.cost-front.scores[i].cost)<1e-8));
}
const edge=S.rectangle('edge',[0,0,0],[1,0,0],[0,0,1],[-4,4,-4,0]);
const edgeChoice=select(base,[0,0,2],edge);
check('Forward foot off platform is unavailable',!edgeChoice.scores[0].eligible&&edgeChoice.scores[1].eligible);
check('Valid rear contact wins over missing front contact',side(edgeChoice)==='R');
check('Explicit invalid foot remains explicit',side(select(base,[0,0,2],edge,{...settings,jumpFoot:'L'}))==='L');
check('Far theoretical target cannot replace cone contact',side(select(base,[0,0,2],floor,{...settings,supportAlpha:1000}))==='L');
check('Scalar velocity matches vector callers',side(S.candidates(base,m.names,settings,floor,2))===side(select(base,R.rotate(base.q[0],[0,0,2]))));
const snapshot=JSON.stringify(front);select(pose({gapL:.3}));check('Selection has no playback history',JSON.stringify(select(base))===snapshot);
const old=JSON.parse(fs.readFileSync(new URL('data/cone-choice-case.json',import.meta.url)));old.pose.axes=old.pose.q.map(R.toAxes);
const oldSurface=S.platformSurface(old.surface),oldSettings=C.sanitize(old.settings),oldChoice=select(old.pose,old.velocity,oldSurface,oldSettings),oldPlan=S.plan(old.pose,old.names,old.parents,oldSettings,oldSurface,0,null,old.velocity);
check('Earlier inclined-cone regression still chooses right',side(oldChoice)==='R'&&oldPlan.leg.side==='R'&&oldPlan.jumpDelay===0);
const far=S.rectangle('far',[0,-50,0],[1,0,0],[0,0,1],[-100,100,-100,100]);
check('Unreachable surface stays unavailable',select(base,[0,0,2],far).scores.every(s=>!s.eligible));
let groundedComparisons=0;const gaitFloor=S.rectangle('gait',[0,0,0],[1,0,0],[0,0,1],[-50,50,-50,50]);
for(const gait of ['walk','run']){
 const run=F.decodeNN(JSON.parse(fs.readFileSync(new URL('data/'+gait+'-default-drawn.json',import.meta.url))));
 for(let i=1;i<=48;i++){
  const t=i/60,p=F.at(run,t,m.parents),v=R.mul(R.sub(F.at(run,t+.001,m.parents).points[0],F.at(run,t-.001,m.parents).points[0]),500),c=select(p,v,gaitFloor);
  const perturbed={...p,points:p.points.map((v,j)=>j===0?v:R.add(v,[1e-6,-1e-6,1e-6]))};
  if(Math.abs(c.scores[0].cost-c.scores[1].cost)>.002)check(gait+' real pose stable under micron noise '+i,side(select(perturbed,v,gaitFloor))===side(c));
  if(c.scores.every(s=>s.eligible&&s.contactDistance<.05)&&Math.abs(c.scores[0].forwardLead-c.scores[1].forwardLead)>.3){
   check(gait+' real grounded stride favors front '+i,c.selected===(c.scores[0].forwardLead>c.scores[1].forwardLead?0:1));groundedComparisons++;
  }
 }
}
check('Real gait fixtures include grounded comparisons',groundedComparisons>0);
console.log(JSON.stringify({passed:true,checks:checks.length,groundedComparisons,firstRearHeight:heightSweep.find(r=>r.chosen==='R')?.height,example:front.scores.map(s=>({foot:s.foot,contactDistance:s.contactDistance,forwardLead:s.forwardLead,cost:s.cost}))},null,2));
