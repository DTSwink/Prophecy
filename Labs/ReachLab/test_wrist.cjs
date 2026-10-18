const assert=require('node:assert/strict'),R=require('../SwordHolsterLab/recovery.js'),W=require('./wrist.js');
const {qm,qinv,unit,qexp}=R,phat=require('./phat.json');let worst=0,cases=0;
for(const x of [0,1,2])for(const y of [0,1,2])for(const z of [0,1,2])for(let i=0;i<90;i++){
 const q=unit(qm(qexp([i*.73,0,0]),qexp([0,i*.31,i*.57]))),m=[x,y,z],lim=[30,23.71,50],p=W.project(q,m,lim),again=W.project(p,m,lim);
 assert(p.every(Number.isFinite));assert(Math.abs(Math.hypot(...p)-1)<1e-10);
 const e=Math.min(Math.hypot(...p.map((v,j)=>v-again[j])),Math.hypot(...p.map((v,j)=>v+again[j])));worst=Math.max(worst,e);assert(e<1e-10);
 if(m.every(v=>v===0))assert.deepEqual(q,p);
 if(m.every(v=>v===2))assert(Math.abs(p[3])>1-1e-12);
 for(const j of phat.wrists){const a=qexp([.3,-.5,.2]),h=W.constrain(j,a,q),h2=W.constrain(j,a,h);assert(Math.abs(R.dot(h,h2))>1-1e-10);}cases++;
}
console.log(JSON.stringify({passed:true,cases,maxIdempotenceQuaternionError:worst}));
