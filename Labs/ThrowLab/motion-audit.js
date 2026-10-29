// Offline motion audit. No playback loop, filtering, or runtime pose changes.
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
function scan({sample,end,names,step=.25}){
 const cache=new Map(),pose=f=>{f=Math.max(0,Math.min(end,f));const key=f.toFixed(9);if(!cache.has(key))cache.set(key,sample(f));return cache.get(key);};
 function measure(f,h){
  const a=pose(f-h),b=pose(f),c=pose(f+h);let worst={score:0,frame:f};
  for(let j=0;j<names.length;j++){
   const before=R.mul(R.sub(b.points[j],a.points[j]),60/h),after=R.mul(R.sub(c.points[j],b.points[j]),60/h);
   const wb=R.mul(R.qlog(R.qm(b.q[j],R.qinv(a.q[j]))),60/h),wa=R.mul(R.qlog(R.qm(c.q[j],R.qinv(b.q[j]))),60/h);
   const linear=R.length(R.sub(after,before)),angular=R.length(R.sub(wa,wb)),score=Math.max(linear/.15,angular/2);
   if(score>worst.score)worst={frame:f,bone:names[j],score,linearJump:linear,angularJump:angular,speedBefore:R.length(before),speedAfter:R.length(after)};
  }
  return worst;
 }
 const coarse=[];for(let f=step;f<end-step;f+=step)coarse.push(measure(f,step));
 const peaks=coarse.filter((r,i)=>r.score>1&&r.score>=(coarse[i-1]?.score||0)&&r.score>=(coarse[i+1]?.score||0));
 const discontinuities=[];
 for(const peak of peaks){
  let f=peak.frame,h=step;
  for(let k=0;k<8;k++){
   const candidates=[-1,-.5,0,.5,1].map(offset=>measure(f+offset*h,h/2));
   const best=candidates.reduce((a,b)=>a.score>b.score?a:b);f=best.frame;h/=2;
  }
  const fine=measure(f,h),wide=measure(f,h*4);
  // Smooth acceleration shrinks with the probe interval; a velocity jump does not.
  if(fine.score>1&&fine.score>wide.score*.6&&!discontinuities.some(r=>Math.abs(r.frame-f)<step))discontinuities.push({...fine,probeFrames:h});
 }
 return {samples:cache.size,discontinuities:discontinuities.sort((a,b)=>b.score-a.score)};
}
const api={scan};if(typeof module!=='undefined')module.exports=api;else root.ThrowMotionAudit=api;
})(globalThis);
