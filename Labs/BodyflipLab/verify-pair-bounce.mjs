// Pure numeric bounce tests: no UI, model, files from active scenes, or HTTP.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),B=require('./bounce.js');
const {add,sub,mul,length,dot}=R,dist=(a,b)=>length(sub(a,b)),checks=[];
const check=(label,value)=>{assert(value,label);checks.push(label);};
const carry=(v,n,d)=>{const line=R.cross(n,d),n2=dot(line,line);return n2>1e-12?mul(line,dot(v,line)/n2):sub(v,mul(n,dot(v,n)));};
const legacy={root:[0,1,0],hip:[0,1,0],foot:[0,0,0],normal:[0,1,0],direction:[0,1,0],incoming:[0,-4,0],reach:1.2,maxReach:1.188,loadMs:100,rebound:.5,launchSpeed:4.5,cap:20,rolling:()=>({foot:[0,0,0],valid:true}),carry};
const receipt=[];for(const loadMs of [50,100,200])for(const impact of [0,2,5,15]){const b=B.create({...legacy,loadMs,incoming:[0,-impact,0]}),samples=Array.from({length:181},(_,i)=>b.sample(i/60));receipt.push({loadMs,impact,load:b.loadDuration,release:b.releaseTime,didPush:b.didPush,compression:b.compression,returnedEnergy:b.returnedEnergy,limitReason:b.limitReason,frames:b.frames,samples});}
check('All twelve original single-limb motions remain bit-identical',crypto.createHash('sha256').update(JSON.stringify(receipt)).digest('hex')==='a379852c4206cf2dfdec2c368e0fd56fabb1dd0209e0b79159a4c6d907da7dc3');
const base={...legacy,root:[0,0,0],hip:[0,.7,0],foot:[0,0,0],incoming:[0,-2,0],reach:1,maxReach:.99,anchorOffset:()=>[0,.7,0],surfaceOrigin:[0,0,0]};
const pair=(rightReach=.99)=>p=>[-1,1].map((side,i)=>({hip:add(p,[side*.2,.7,0]),foot:[side*.2,0,0],maxReach:i?rightReach:.99,minLength:.45,valid:true,normal:[0,1,0],surfaceOrigin:[0,0,0]}));
const plane=(p,delta)=>{const next=add(p,delta),hit=next[1]<0;return {root:[next[0],Math.max(0,next[1]),next[2]],contacts:hit?[{normal:[0,1,0]}]:[]};};
function inspect(label,config){
 const b=B.create(config);let error=0,minHeight=Infinity;
 for(let i=0;i<=Math.ceil(b.releaseTime*1920);i++){
  const t=Math.min(i/1920,b.releaseTime),f=b.sample(t);assert(f.p.every(Number.isFinite)&&f.v.every(Number.isFinite),label+' finite');
  for(const c of config.constraints(f.p,t)){const d=dist(c.hip,c.foot);error=Math.max(error,d-c.maxReach,(c.minLength??0)-d);minHeight=Math.min(minHeight,c.hip[1]);}
  if(config.resolveRoot)check(label+' capsule clearance '+i,f.p[1]>=-1e-8);
 }
 check(label+' both arms stay within reach at subframes',error<1e-7);
 check(label+' no shoulder passes through contact plane',minHeight>=-1e-8);
 const at=b.releaseTime+.2,expected=JSON.stringify(b.sample(at));b.sample(10);b.sample(0);check(label+' deterministic seeking',JSON.stringify(b.sample(at))===expected);
 return b;
}
const symmetric=inspect('Symmetric',{...base,constraints:pair()}),single=B.create(base);
check('Two symmetric contacts do not double the launch impulse',dist(symmetric.released.v,single.released.v)<1e-9&&symmetric.releaseTime===single.releaseTime);
const asymmetric=inspect('Short right arm',{...base,incoming:[0,0,0],constraints:pair(.701)}),unboundedArm=B.create({...base,incoming:[0,0,0]});
check('Tighter actual arm ends push before mean-arm boundary',asymmetric.releaseTime<unboundedArm.releaseTime);
check('The shorter arm reaches its own release boundary',Math.abs(dist(pair(.701)(asymmetric.released.p)[1].hip,[.2,0,0])-.701)<1e-6);
inspect('Capsule plus arms',{...base,resolveRoot:plane,constraints:pair(.78)});
const sliding=B.create({...base,root:[.02,.01,0],hip:[.02,.7,0],incoming:[100,-6,0],anchorOffset:()=>[0,.69,0],resolveRoot:plane,constraints:p=>[-1,1].map(side=>({hip:add(p,[side*.2,.69,0]),foot:[side*.2,0,0],maxReach:.701,valid:true}))});
check('A feasible capsule-tangent correction is not mistaken for disjoint reach',sliding.frames.length>1&&sliding.limitReason!=='No shared reach'&&Math.abs(sliding.frames.at(-1).p[1])<1e-8&&Math.hypot(sliding.frames.at(-1).p[0],.69)<=.701+1e-8);
const velocityBase={...base,root:[.02,.01,0],hip:[.02,.7,0],incoming:[100,-6,0],anchorOffset:()=>[0,.69,0],resolveRoot:plane};
const oneVelocity=B.create({...velocityBase,constraints:p=>[{hip:add(p,[0,.69,0]),foot:[0,0,0],maxReach:.701,valid:true}]}),duplicateVelocity=B.create({...velocityBase,constraints:p=>Array.from({length:2},()=>({hip:add(p,[0,.69,0]),foot:[0,0,0],maxReach:.701,valid:true}))});
check('Duplicating an active arm axis cannot brake or reverse velocity twice',dist(oneVelocity.frames.at(-1).v,duplicateVelocity.frames.at(-1).v)<1e-8);
check('Joint velocity projection respects both capsule and active arm bounds',duplicateVelocity.frames.at(-1).v[1]>=-1e-10&&dot(duplicateVelocity.frames.at(-1).v,R.unit(add(duplicateVelocity.frames.at(-1).p,[0,.69,0])))<=1e-7);
const coupledConstraints=p=>[-1,1].map(side=>({hip:add(p,[0,.6,0]),foot:[side*.8,0,0],maxReach:1,valid:true}));
const coupled=B.create({...base,hip:[0,.6,0],incoming:[2,3,0],anchorOffset:()=>[0,.6,0],constraints:coupledConstraints}),coupledFrame=coupled.frames.at(-1);
check('Coupled nonparallel arm axes converge without outward velocity',coupledConstraints(coupledFrame.p).every(c=>dot(coupledFrame.v,R.unit(sub(c.hip,c.foot)))<1e-8));
check('Coupled projection does not invent reversed motion',length(coupledFrame.v)<1e-8);
const moving=t=>[0,.7+.15*t,0],movingPair=(p,t)=>[-1,1].map((side,i)=>({hip:add(p,[side*.2,moving(t)[1],0]),foot:[side*.2,0,side*.02*t],maxReach:i?.8:.9,minLength:.45,valid:true,normal:[0,1,0],surfaceOrigin:[0,0,0]}));
inspect('Moving shoulders and wrists',{...base,anchorOffset:moving,constraints:movingPair});
const disjoint=B.create({...base,constraints:p=>[-1,1].map(side=>({hip:add(p,[side*.2,.7,0]),foot:[side*2,0,0],maxReach:.3,valid:true}))});
check('Disjoint reach volumes produce no push',!disjoint.didPush&&disjoint.limitReason==='No shared reach'&&disjoint.loadDuration===0);
check('Impossible pair preserves passive velocity and initial position',dist(disjoint.released.v,base.incoming)<1e-12&&dist(disjoint.sample(0).p,base.root)<1e-12);
const blocked=B.create({...base,anchorOffset:t=>[0,.7+20*t,0],resolveRoot:plane,constraints:(p,t)=>[-1,1].map(side=>({hip:add(p,[side*.2,.7+20*t,0]),foot:[side*.2,0,0],maxReach:.71,valid:true}))});
check('Capsule/reach conflict stops before an infeasible load frame',!blocked.didPush&&blocked.limitReason==='No shared reach'&&blocked.frames.length===1);
check('Blocked pair cannot acquire an active launch impulse',dist(blocked.released.v,base.incoming)<1e-12&&blocked.returnedEnergy===0);
const lost=B.create({...base,constraints:(p,t)=>pair()(p).map((c,i)=>({...c,valid:i===0||t<.002}))});
check('Either lost contact aborts the pair without pushing',!lost.didPush&&lost.limitReason==='Contact lost');
console.log(JSON.stringify({passed:true,checks:checks.length,symmetricRelease:symmetric.releaseTime,asymmetricRelease:asymmetric.releaseTime}));
