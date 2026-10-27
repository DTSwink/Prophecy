import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),M=require('./jump-motion.js'),R=require('./recovery.js'),I=require('./idle.js'),Scenes=require('./scenes.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),parents=m.parents,names=m.names,jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const bytes=fs.readFileSync(new URL('data/idle.bin',import.meta.url)),idle=I.create(read('data/idle.json'),bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m).motion();
const response=await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:0,drawn:true})});assert(response.ok);const run=F.decodeNN(await response.json());
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
const distance=(a,b)=>R.length(R.sub(a,b)),error=(a,b)=>Math.max(...a.points.map((p,i)=>distance(p,b.points[i]))),qError=(a,b)=>1-Math.abs(a.reduce((n,v,i)=>n+v*b[i],0)),local=p=>R.localize(p.points,p.q,parents);
const event={id:'first',time:.9,surface:'floor'},floor={id:'floor',position:[0,-.2,0],size:[40,.4,60],rotation:[0,0,0,1]};
const settings=C.sanitize({mode:'jump',ramps:false,platforms:[floor],jumpEvents:[event]});
const started=performance.now(),base=F.sequence(run,jumps,settings,parents),b=base.segments[0];
check('Unconfigured jump allocates no choreography',b.motion===null);
const corrupt=C.sanitizeJump({flip:NaN,twist:Infinity,turnDuration:0,turnDelay:-1,turnAxis:90,pose:'unknown',poseIn:0,poseOut:-3});
check('Bad settings recover to finite safe timing',corrupt.flip===0&&corrupt.twist===0&&corrupt.turnDelay===0&&corrupt.turnDuration===1/60&&corrupt.turnAxis===null&&corrupt.pose==='none'&&corrupt.poseIn>0&&corrupt.poseOut>0);
for(const duration of [.3,.8,1.6]){const e=C.sanitizeJump({turnDuration:duration});check('Old saved turn keeps its exact curve '+duration,Array.from({length:101},(_,i)=>Math.abs(M.turnProgress(duration*i/100,e)-M.ease(i/100))<1e-12).every(Boolean));}
const linear=C.sanitizeJump({turnDuration:1,turnIn:0,turnOut:0}),asymmetric=C.sanitizeJump({turnDuration:1,turnIn:.1,turnOut:.4});
check('Zero turn blends give constant angular speed',Array.from({length:101},(_,i)=>Math.abs(M.turnProgress(i/100,linear)-i/100)<1e-12).every(Boolean));
check('Separate turn blend times affect the actual rotation curve',Math.abs(M.turnProgress(.4,asymmetric)-M.ease(.4))>.05);
for(const e of [asymmetric,C.sanitizeJump({turnDuration:.1,turnIn:3,turnOut:5})]){
 const values=Array.from({length:1001},(_,i)=>M.turnProgress(e.turnDuration*i/1000,e));
 check('Turn blends stay monotone and reach the full angle '+e.turnDuration,values[0]===0&&values.at(-1)===1&&values.every((v,i)=>Number.isFinite(v)&&v>=0&&v<=1&&(i===0||v>=values[i-1])));
 const dt=1e-7,fit=Math.min(1,e.turnDuration/(e.turnIn+e.turnOut)),join=e.turnIn*fit;
 check('Changing blend speed has no jump at the cruise boundary '+e.turnDuration,Math.abs((M.turnProgress(join+dt,e)-M.turnProgress(join,e))/dt-(M.turnProgress(join,e)-M.turnProgress(join-dt,e))/dt)<.001);
}
const configured={...event,flip:720,twist:-360,turnDelay:.15,turnDuration:.7,turnAxis:3,pose:'pose1'};
const seq=F.sequence(run,jumps,{...settings,jumpEvents:[configured]},parents),s=seq.segments[0],start=s.airStart;
check('Choreography leaves support and release timing exact',s.jumpStart===b.jumpStart&&start===b.airStart);
let rootError=0,pinError=0;
for(let t=0;t<start+1.4;t+=1/120){const p=s.sample(t),q=b.sample(t);rootError=Math.max(rootError,distance(p.root,q.root));if(t<=start)pinError=Math.max(pinError,error(p.pose,q.pose));}
check('Root trajectory and all pinned frames unchanged',rootError<1e-12&&pinError<1e-12);
check('Delay holds zero turn',s.motion.values(start+.14).flip===0);
check('Half duration reaches half angle without wrapping',Math.abs(s.motion.values(start+.5).flip-360)<1e-8);
check('Full totals retain negative twist and multiple turns',s.motion.values(start+1).flip===720&&s.motion.values(start+1).twist===-360);
const h=1e-6,value=t=>s.motion.values(t).flip;
check('Rotation starts and finishes without angular-velocity jumps',Math.abs(value(start+.15+h)/h)<.001&&Math.abs((value(start+.85)-value(start+.85-h))/h)<.001);
check('Normal and twist both visibly rotate the rig',error(s.sample(start+.5).pose,b.sample(start+.5).pose)>.2);
check('Repeated/reverse seeks give identical poses',(()=>{const p=JSON.stringify(seq.sample(start+.32));seq.sample(8);seq.sample(0);return JSON.stringify(seq.sample(start+.32))===p;})());
check('Planner and displayed sampler use identical choreography',error(seq.sample(start+.32).pose,s.carrier.sample(start+.32).pose)<1e-12);
check('No-pose is a true bypass',M.poseWeight(.3,{...C.jumpDefaults,pose:'none'})===0);
const phases=C.sanitizeJump({pose:'pose1',poseIn:.2,poseHold:.3,poseOut:.25});
check('Pose eases in, holds and eases out',M.poseWeight(0,phases)===0&&Math.abs(M.poseWeight(.1,phases)-.5)<1e-9&&M.poseWeight(.35,phases)===1&&Math.abs(M.poseWeight(.625,phases)-.5)<1e-9&&M.poseWeight(.75,phases)===0);
const rigLegs=['l','r'].map(side=>({k:names.indexOf('calf_'+side),f:names.indexOf('foot_'+side)}));
function knee(p,{k,f}){const l=local(p),u=R.unit(l.p[k]),v=R.unit(R.rotate(l.q[k],l.p[f]));return Math.atan2(-R.cross(u,v)[2],R.dot(u,v))*180/Math.PI;}
const measurements=[];
for(const motion of [run,idle])for(const pose of ['pose1','pose2','pose3','pose4']){
 const opts={...settings,mode:motion===idle?'idle':'jump',jumpEvents:[{...event,pose,flip:360,twist:360,turnDuration:.6}]};
 const p=F.sequence(motion,jumps,opts,parents).segments[0];let min=Infinity,max=-Infinity,boneError=0,maxStep=0,previous=null;
 for(let i=0;i<=300;i++){
  const time=p.airStart+i/240,frame=p.sample(time).pose;
  assert(frame.points.flat().every(Number.isFinite));
  for(const leg of rigLegs){const a=knee(frame,leg);min=Math.min(min,a);max=Math.max(max,a);}
  if(motion===run){const target=local(b.sample(time).pose),actual=local(frame);for(let j=1;j<names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(target.p[j])-R.length(actual.p[j])));}
  if(previous)maxStep=Math.max(maxStep,error(frame,previous));previous=frame;
 }
 check('Safe knee range '+opts.mode+' '+pose,min>=-1e-3&&max<=150.01);
 check('Pose preserves skeleton lengths '+opts.mode+' '+pose,boneError<1e-9);
 const end=p.airStart+C.jumpDefaults.poseIn+C.jumpDefaults.poseHold+C.jumpDefaults.poseOut;
 const without=F.sequence(motion,jumps,{...opts,jumpEvents:[{...opts.jumpEvents[0],pose:'none'}]},parents).segments[0];
 check('Pose fully returns to moving animation '+opts.mode+' '+pose,error(p.sample(end+.01).pose,without.sample(end+.01).pose)<1e-10);
 for(const t of [p.airStart,p.airStart+.2,p.airStart+.5,end]){
  const prev=p.sample(t-h).pose,at=p.sample(t).pose,next=p.sample(t+h).pose;
  const velocityError=Math.max(...at.points.map((v,i)=>distance(R.mul(R.sub(v,prev.points[i]),1/h),R.mul(R.sub(next.points[i],v),1/h))));
  check('Continuous transition '+opts.mode+' '+pose+' '+(t-p.airStart).toFixed(2),velocityError<.15);
 }
 measurements.push({mode:opts.mode,pose,minKnee:min,maxKnee:max,boneError,max240HzStep:maxStep});
}
// Isolate the rigid turn with a fake segment to check axis direction and winding.
const p=b.sample(start+.4).pose,stub={sample:()=>({pose:p,root:p.points[0]}),airStart:1,jumpStart:.9,abortTime:Infinity};
for(const axis of [0,3,6,9]){
 const turn=M.create({...event,flip:90,turnAxis:axis},stub,jumps,names,parents,settings),actual=turn.sample(2).pose;
 const forward=R.rotate(p.q[0],[0,0,1]),heading=R.qexp([0,Math.atan2(forward[0],forward[2]),0]),normal=R.rotate(heading,C.flipAxis(axis));
 const expected=R.qm(R.qexp(R.mul(normal,Math.PI/2)),p.q[1]);
 check('Flip uses selected root-relative axis '+axis,qError(actual.q[1],expected)<1e-10);
}
const turnsOnly=M.create({...event,twist:90},stub,jumps,names,parents,settings).sample(2).pose;
check('Twist stays on the pelvis vertical',qError(turnsOnly.q[1],R.qm(p.q[1],R.qexp([Math.PI/2,0,0])))<1e-10);
const state={settings:{...settings,jumpEvents:[configured]},playback:{time:2,playing:false}},library=Scenes.open(state),copied=Scenes.copy(library,'Other','other');
const pack=Scenes.pack(Scenes.select(Scenes.open(JSON.parse(JSON.stringify(Scenes.pack(copied)))),'original'));
check('Choreography survives scene copy, switch, save and reload',JSON.stringify(pack.settings.jumpEvents)===JSON.stringify(state.settings.jumpEvents));
const result={passed:checks.length,rootError,pinError,measurements,elapsedMs:performance.now()-started,visualVerified:false};
fs.writeFileSync(new URL('jump-motion-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
