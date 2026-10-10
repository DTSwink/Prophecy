const assert=require('node:assert/strict'),H=require('./holster.js'),T=require('./retime.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const nonlinear=[[.15,.04],[.35,.13],[.7,.9],[.88,.97]],linear=T.prepare(T.linear()),curve=T.prepare(nonlinear);
let previous=0;
for(let i=0;i<=1000;i++){
 const x=i/1000,y=T.sample(curve,x);assert(y>=previous-1e-12&&y>=0&&y<=1);previous=y;
 assert(Math.abs(T.sample(linear,x)-x)<1e-12);
}
for(const [x,y] of nonlinear)assert(Math.abs(T.sample(curve,x)-y)<1e-12,'passes through handles');
assert(T.sample(curve,.25)<.25);assert(T.sample(curve,.75)>.75);
assert.deepEqual(T.sanitize([[NaN,0]]),T.linear());
const invalid=T.sanitize([[.9,.8],[.1,.2],[.5,-1],[2,2]]);for(let i=1;i<4;i++)assert(invalid[i][0]>invalid[i-1][0]&&invalid[i][1]>=invalid[i-1][1]);
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const original=H.prepare(data,setup,{motion,sheathe});
 const action=sheathe?'sheathe':'draw',otherAction=sheathe?'draw':'sheathe';
 const retimed=H.prepare(data,setup,{motion,sheathe,[action+'Curve']:nonlinear,[action+'SlideCurve']:nonlinear});
 assert.deepEqual(retimed.sourceFrames,original.sourceFrames,'retiming must not change prepared body/arm motion');

 const start=original.o.startTick/60,end=original.playbackDuration,head=data.names.indexOf('head');
 for(const f of original.frames){
  const base=H.motion(data,motion,f.tick/60);
  if(f.headLook.mode==='Forward'||f.headLook.mode==='Idle')assert(H.angle(f.pose[head].q,base[head].q)<.001,'head returns to authored forward facing');
 }
 const reach=retimed.retimeSegments.reach,slide=retimed.retimeSegments.slide;
 const quarter=s=>s.start+(s.end-s.start)*.25;
 for(const t of [0,start,quarter(reach),reach.end,quarter(slide),slide.end,end]){
  const source=H.recordedTime(retimed,t),a=H.sample(retimed,t),b=H.sample(original,source);
  if(a.fkReturn||b.fkReturn)continue;
  for(let j=0;j<data.names.length;j++)if(!['neck_01','neck_02','head'].includes(data.names[j]))assert.deepEqual(a.pose[j],b.pose[j],'body/arm share recorded frame');
  assert.deepEqual(a.sword,b.sword,'equipment shares body time');
 }
 assert.equal(H.recordedTime(retimed,start),start);assert.equal(H.recordedTime(retimed,end),end);
 for(const segment of [reach,slide])assert(H.recordedTime(retimed,quarter(segment))<quarter(segment)-.01,'each phase retimed');
 const reachOnly=H.prepare(data,setup,{motion,sheathe,[action+'Curve']:nonlinear});
 const slideOnly=H.prepare(data,setup,{motion,sheathe,[action+'SlideCurve']:nonlinear});
 assert.equal(H.recordedTime(reachOnly,quarter(slide)),quarter(slide),'reach curve leaves sliding unchanged');
 assert.equal(H.recordedTime(slideOnly,quarter(reach)),quarter(reach),'sliding curve leaves reaching unchanged');
 assert.equal(H.recordedTime(retimed,(slide.end+end)/2),(slide.end+end)/2,'unshrink timing unchanged');
 const other=H.prepare(data,setup,{motion,sheathe,[otherAction+'Curve']:nonlinear,[otherAction+'SlideCurve']:nonlinear});
 for(const segment of [reach,slide])assert.equal(H.recordedTime(other,quarter(segment)),quarter(segment),'curves independent per action');
}
const legacy=H.sanitize({drawCurve:nonlinear});assert.deepEqual(legacy.drawCurve,nonlinear);assert.deepEqual(legacy.drawSlideCurve,T.linear());
for(const input of [{startTick:800},{maxReachSpeed:.01},{spineClavicleAngleLimit:0,shrinkPercent:0},{duration:3}]){
 const m=H.prepare(data,setup,{...input,drawCurve:nonlinear,sheatheCurve:nonlinear,drawSlideCurve:nonlinear,sheatheSlideCurve:nonlinear});
 let previous=-1;for(let i=0;i<=300;i++){const t=m.playbackDuration*i/300,s=H.recordedTime(m,t);assert(s>=previous&&s>=0&&s<=m.playbackDuration);previous=s;}
 assert.equal(H.recordedTime(m,m.playbackDuration),m.playbackDuration);
}
console.log('PASS: independent reach/slide curves for both actions, fixed phase boundaries, unchanged unshrink, shared poses/equipment, legacy settings, truncated/unreachable actions and head compensation.');
