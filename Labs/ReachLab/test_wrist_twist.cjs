const assert=require('assert/strict'),R=require('../SwordHolsterLab/recovery.js'),W=require('./wrist.js'),{unit,qm,qinv,qexp,rotate,dot,mul,fromTo}=R;
let seed=32451;const rand=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296),q=()=>unit(Array.from({length:4},()=>rand()*2-1));
let cases=0,maxError=0,maxDirection=0,intervals=0;const timing=[];
for(const modes of [[1,1,1],[0,0,0],[2,2,2],[2,1,1],[1,2,1],[1,1,2]])for(let n=0;n<120;n++){
 const j={handFirst:n%2===0,frame1:q(),frame2:q(),modes,limits:[15+rand()*100,15+rand()*100,15+rand()*100]},desired=q(),local=unit([rand()*2-1,rand()*2-1,rand()*2-1]);
 const witness=W.constrain({...j,handFirst:!j.handFirst},desired,q()),direction=rotate(witness,local),prior=(rand()*2-1)*Math.PI;
 const t=performance.now(),fit=W.fitForearm(j,desired,local,direction,prior);timing.push(performance.now()-t);intervals+=fit.intervalSolve;cases++;
 const error=1-Math.abs(dot(desired,W.constrain(j,fit.forearm,desired))),directionError=R.length(R.sub(rotate(fit.forearm,local),direction));maxError=Math.max(maxError,error);maxDirection=Math.max(maxDirection,directionError);
 assert(fit.feasible,'Known feasible direction '+modes+' case '+n);assert(error<2e-11,'PHAT violation');assert(directionError<1e-8,'Twist moved the elbow');
}
timing.sort((a,b)=>a-b);console.log(JSON.stringify({passed:true,cases,maxError,maxDirection,intervals,meanMs:timing.reduce((a,b)=>a+b,0)/cases,p95Ms:timing[Math.floor(cases*.95)]}));
