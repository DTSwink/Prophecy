// Pure numeric reservation tests; no NN, UI, state files or workers.
import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),B=require('./bounce.js'),R=require('./recovery.js');
const {add,sub,mul,dot,length}=R,checks=[],check=(label,value)=>{assert(value,label);checks.push(label);};let reserved=0;
const reports=[];
for(const angle of [0,Math.PI/4])for(const impact of [2,5,8])for(const launchSpeed of [1.5,3,5])for(const paired of [false,true]){
 const n=[Math.sin(angle),Math.cos(angle),0],origin=[0,0,0],initial=add(mul(n,-impact),[0,0,1.2]),reach=.55,rest=.5,minLength=Math.max(.45*reach,rest-.25*reach);let committed=null;
 const anchor=t=>{const u=Math.min(1,(committed??t)/.2),smooth=u*u*u*(10+u*(-15+6*u));return mul(n,rest-.08*smooth);};
 const feet=[[-.08,0,0],[.08,0,0]],constraints=paired?(p,t)=>feet.map(foot=>({foot,hip:add(add(p,anchor(t)),foot),maxReach:reach*.99,minLength,valid:true,normal:n,surfaceOrigin:[0,0,0]})):null;
 const relativeImpact=Math.max(0,-dot(add(initial,mul(sub(anchor(1/960),anchor(0)),960)),n));
 const b=B.create({root:origin,hip:mul(n,rest),foot:[0,0,0],normal:n,direction:n,incoming:initial,reach,maxReach:reach*.99,loadMs:100,buildMs:200,rebound:.5,launchSpeed,cap:20,anchorOffset:anchor,startPush:t=>{committed=t;},rolling:()=>({foot:[0,0,0],valid:true}),loading:()=>({foot:[0,0,0],valid:true}),carry:v=>sub(v,mul(n,dot(v,n))),constraints,surfaceOrigin:[0,0,0]});
 const name=[angle,impact,launchSpeed,paired].join('/');let error=0;
 for(let i=0;i<=Math.ceil(b.releaseTime*1920);i++){const t=Math.min(b.releaseTime,i/1920),f=b.sample(t),d=length(add(f.p,anchor(t)));error=Math.max(error,minLength-d,d-reach*.99);assert(f.p.every(Number.isFinite)&&f.v.every(Number.isFinite));}
 check(name+' complete motion stays within limb travel',error<1e-7);
 const energy=.5*relativeImpact*relativeImpact+9.81*(origin[1]-b.frames.at(-1).p[1]);check(name+' rebound does not exceed accumulated available energy',b.returnedEnergy<=energy*.5+1e-8&&b.returnedEnergy<=.5*launchSpeed**2+1e-8);
 for(const f of b.frames){const expected=add(mul(initial,f.t),[0,-4.905*f.t*f.t,0]);assert(length(sub(f.p,expected))<1e-8,name+' buildup preserves ballistic momentum');}
 if(b.limitReason==='Push travel reserved'){reserved++;check(name+' reserved drive completes outward',dot(b.released.v,n)>0&&b.releaseTime-b.loadDuration>.008);}
 const p=b.sample(b.releaseTime+.1),v=b.released.v,t=.1;check(name+' release remains ballistic',length(sub(p.p,add(b.released.p,add(mul(v,t),[0,-4.905*t*t,0]))))<1e-8);
 reports.push({impact,launchSpeed,paired,slope:angle,load:b.loadDuration,drive:b.releaseTime-b.loadDuration,reserved:b.limitReason==='Push travel reserved'});
}
check('Matrix exercises travel reservation',reserved>0);
console.log(JSON.stringify({passed:true,checks:checks.length,cases:reports.length,reserved},null,2));
