const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const H=require('./holster.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const curves=[[[.2,.02],[.4,.1],[.6,.9],[.8,.98]],[[.2,0],[.4,0],[.6,.1],[.8,.7]]];
const dist=(a,b)=>R.length(R.sub(a,b)),local=p=>R.localize(p.map(v=>v.p),p.map(v=>v.q),data.parents);
const lower=data.names.map((n,j)=>/^(root|pelvis|thigh|calf|foot|ball)/.test(n)?j:-1).filter(j=>j>=0);
const left=data.names.map((n,j)=>/^(upperarm|lowerarm|hand)_l$/.test(n)?j:-1).filter(j=>j>=0);
let cases=0,maxBaseError=0,maxGripError=0;
for(const sheathe of [true,false]){
 const action=sheathe?'sheathe':'draw',original=H.prepare(data,setup,{motion:'walk',sheathe,gazeYaw:35,duration:12});
 for(const curve of curves){
  const m=H.retime(original,{...original.o,[action+'Curve']:curve,[action+'SlideCurve']:curve});
  assert.equal(m.sourceFrames,original.sourceFrames,'curve edit reuses source planning');
  for(let tick=0;tick<=m.completionTick;tick+=.37){
   const t=tick/60,f=H.sample(m,t),base=H.motion(data,'walk',t,35),a=local(f.pose),b=local(base);
   for(const j of lower){const error=dist(f.pose[j].p,base[j].p);maxBaseError=Math.max(maxBaseError,error);assert(error<1e-7,`base clock position ${action} ${tick} ${data.names[j]} ${error}`);assert(H.angle(f.pose[j].q,base[j].q)<1e-5);}
   if(t<m.fkReturn.start||t>m.playbackDuration-.001)for(const j of left){assert(dist(a.p[j],b.p[j])<1e-7,'left arm NN offsets');assert(H.angle(a.q[j],b.q[j])<1e-5,'left arm NN rotations');}
   const holster=H.compose(m.holsterLocal,base[m.pelvis]);assert(dist(f.holster.p,holster.p)<1e-7,'holster keeps real gait clock');assert(H.angle(f.holster.q,holster.q)<1e-5);
   if(f.phase==='Slide'){maxGripError=Math.max(maxGripError,f.handError);assert(f.handError<.6,'arm tracks steady moving holster');}
  }
  for(const edge of [m.o.startTick/60,m.plan.endTick/60,m.plan.slideEnd/60,m.fkReturn.start]){if(Math.abs(edge/data.motions.walk.duration-Math.round(edge/data.motions.walk.duration))<1e-8)continue; // Imported loop has its own small endpoint mismatch.
const a=H.sample(m,edge-1e-7),b=H.sample(m,edge+1e-7);for(let j=0;j<data.names.length;j++){assert(dist(a.pose[j].p,b.pose[j].p)<.001,`continuous position ${action} ${cases} edge=${edge} bone=${data.names[j]} distance=${dist(a.pose[j].p,b.pose[j].p)}`);assert(H.angle(a.pose[j].q,b.pose[j].q)<.01,'continuous rotation at phase boundary');}}
  cases++;
 }
}
// Solves are preparation work only, including the new moving-holster guides.
const context={module:{exports:{}},require,solves:0};vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('./holster.js'),'utf8').replace('function solve(pose,idx,goal){','function solve(pose,idx,goal){solves++;'),context);
const model=context.module.exports.prepare(data,setup,{motion:'walk',sheathe:false,drawCurve:curves[0],drawSlideCurve:curves[0]}),count=context.solves;
for(let t=0;t<model.playbackDuration;t+=.007)context.module.exports.sample(model,t);
assert.equal(context.solves,count,'playback performs no IK');
console.log(JSON.stringify({passed:true,cases,maxBaseError,maxGripError,noPlaybackSolves:true}));
