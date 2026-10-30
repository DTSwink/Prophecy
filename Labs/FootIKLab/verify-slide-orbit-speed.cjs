'use strict';
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const {slideBalanceTime:clock}=require('./surface.js');
let min=Infinity,max=0,quiet=0,bursts=0,active=false,maxRateStep=0,previousRate=1;
const h=1e-4;
for(let i=0;i<=20000;i++){
 const t=i/1000,rate=(clock(t+h)-clock(t-h))/(2*h);
 min=Math.min(min,rate);max=Math.max(max,rate);
 if(Math.abs(rate-1)<1e-6)quiet++;
 const next=rate>1.01;if(next&&!active)bursts++;active=next;
 maxRateStep=Math.max(maxRateStep,Math.abs(rate-previousRate));previousRate=rate;
 assert(rate>=1-1e-7&&rate<=3.4+1e-6,'Clock only speeds up, then returns to 1x');
 assert.equal(clock(t),clock(t),'Repeatable time mapping without state or random frame noise');
 if(t<=.7)assert.equal(clock(t),t,'Initial pose blend keeps its original timing');
}
assert(max>2.5&&bursts>=10,'Visible repeated bursts');
assert(quiet>3000,'Quiet spans genuinely return to 1x');
assert(maxRateStep<.05,'No abrupt rate reset at a burst or cell boundary');
for(let i=1;i<16;i++){
 const t=.7+i*1.25;
 assert(Math.abs(clock(t+h)-2*clock(t)+clock(t-h))<1e-8,'Continuous integrated clock across completed bursts');
}
const report={passed:true,minRate:min,maxRate:max,bursts,quietSeconds:quiet/1000,maxRateStepPerMillisecond:maxRateStep};
fs.writeFileSync(path.join(__dirname,'snapshots/slide-orbit-speed-verification.json'),JSON.stringify(report,null,2));console.log(report);
