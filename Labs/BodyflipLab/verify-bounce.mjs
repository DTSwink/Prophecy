import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js'),B=require('./bounce.js');
const checks=[],measurements=[],check=(n,v)=>{assert(v,n);checks.push(n);},dist=(a,b)=>R.length(R.sub(a,b));
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json'),run=F.decodeNN(read('data/roll-check.json')),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
check('Only two bounce settings, with proposed defaults',C.defaults.loadMs===100&&C.defaults.rebound===.5);
check('Settings clamp invalid/extreme values',C.sanitize({loadMs:-1,rebound:2}).loadMs===0&&C.sanitize({loadMs:400,rebound:-1}).loadMs===300&&C.sanitize({rebound:-1}).rebound===0);
const base={root:[0,1,0],hip:[0,1,0],foot:[0,0,0],normal:[0,1,0],direction:[0,1,0],incoming:[0,-4,0],reach:1.2,maxReach:1.188,loadMs:100,rebound:.5,launchSpeed:4.5,cap:20,rolling:()=>({foot:[0,0,0],valid:true}),carry:F.carryVelocity};
for(const loadMs of [50,100,200])for(const impact of [0,2,5,15]){
 const b=B.create({...base,loadMs,incoming:[0,-impact,0]}),label=loadMs+'/'+impact;
 check('Initial velocity preserved '+label,dist(b.sample(0).v,[0,-impact,0])<1e-10);
 check('Root and velocity continuous into push '+label,dist(b.sample(b.loadDuration-1e-7).p,b.sample(b.loadDuration).p)<1e-4&&dist(b.sample(b.loadDuration-1e-7).v,b.sample(b.loadDuration).v)<1e-3);
 check('Release is position/velocity continuous '+label,dist(b.sample(b.releaseTime-1e-7).p,b.sample(b.releaseTime+1e-7).p)<1e-4&&dist(b.sample(b.releaseTime-1e-7).v,b.sample(b.releaseTime+1e-7).v)<1e-3);
 check('Loading compresses, with bounded leg '+label,b.compression>0&&b.frames.every(f=>f.p[1]>=.7-1e-8));
 check('Compression limit still permits active extension '+label,b.released.v[1]>4);
 check('Stored impact energy cannot amplify without bound '+label,b.returnedEnergy<=.5*base.launchSpeed**2+1e-8);
 check('Fall remains capped and finite '+label,b.sample(30).v[1]===-20&&b.sample(30).p.every(Number.isFinite));
 check('Seek history cannot change bounce '+label,JSON.stringify(b.sample(.1))===JSON.stringify((b.sample(20),b.sample(0),b.sample(.1))));
 measurements.push({loadMs,impact,loadSeconds:b.loadDuration,compression:b.compression,rebound:b.returnedEnergy,releaseVelocity:b.released.v});
}
const tight=B.create({...base,root:[0,.55,0],hip:[0,.55,0],reach:1,maxReach:.99,incoming:[0,-20,0],loadMs:1});
check('Short leg/hard impact stays finite',tight.sample(.5).p.every(Number.isFinite)&&R.length(tight.sample(.5).v)<30);
const soft=B.create({...base,loadMs:160}),stiff=B.create({...base,loadMs:60}),absorbed=B.create({...base,rebound:0}),elastic=B.create({...base,rebound:1});
check('Longer loading response visibly compresses more',soft.compression>stiff.compression&&soft.loadDuration>stiff.loadDuration);
check('Rebound changes returned energy and launch speed',elastic.returnedEnergy>absorbed.returnedEnergy&&elastic.released.v[1]>absorbed.released.v[1]);
check('No rebound still has an active jump',absorbed.released.v[1]>4);
const source=F.at(run,.5,m.parents),leg=S.leg(source,run.names,'L');
for(const n of [[0,1,0],[Math.SQRT1_2,Math.SQRT1_2,0],[1,0,0]]){
 const turn=R.fromTo([0,1,0],n),source0={points:source.points.map(p=>R.rotate(turn,p)),q:source.q.map(q=>R.qm(turn,q))};source0.axes=source0.q.map(R.toAxes);const leg0=S.leg(source0,run.names,'L');
 const normal=n,axis=n[1]>.5?[0,0,1]:[0,1,0],u=R.unit(R.cross(normal,axis)),v=R.cross(u,normal),point=R.add(source0.points[leg0.foot],S.lowestOffset(source0,leg0,normal)),surface=S.rectangle('test',point,u,v,[-10,10,-10,10]);
 const incoming=R.add(R.mul(normal,-3),[0,0,.3]),poseAt=t=>({...source0,points:source0.points.map(p=>R.add(p,R.mul(incoming,t)))}),settings={...C.defaults,jumpFoot:'L',supportAlpha:0,supportTrigger:.05,loadMs:100};
 const f=F.create(run,jumps,settings,m.parents,source,{time:0,surface,poseAt,velocityAt:()=>incoming});
 check('Inclined/wall contact creates loading '+n,!!f.bounce&&f.jumpStart>f.contactTime);
 const mid=f.contactTime+f.bounce.loadDuration/2,a=f.sample(mid),l=f.support.leg;
 check('Loading labels and rolling contact '+n,a.phase==='LOAD'&&dist(a.pose.points[l.foot],f.contactMotion.sample(mid-f.contactTime).foot)<1e-5);
 check('Loading starts without root velocity impulse '+n,dist(R.mul(R.sub(f.sample(1e-6).root,f.sample(0).root),1e6),incoming)<.01);
 check('No push arrow before extension '+n,f.pushDebug(mid)===null&&!!f.pushDebug(f.jumpStart));
 check('Three-frame arrow anchored to extension '+n,!!f.pushDebug(f.jumpStart+2/60)&&!f.pushDebug(f.jumpStart+3/60));
 check('Animation leg waits for extension '+n,!f.animationLeg(mid,a.pose)&&!!f.animationLeg(f.jumpStart,f.sample(f.jumpStart).pose));
 check('Air time starts at actual release '+n,f.sample(f.jumpStart+f.release/2).airTime===0&&f.sample(f.airStart+.01).airTime>0);
 let error=0;for(let t=0;t<f.airStart;t+=1/480){const p=f.sample(t).pose;error=Math.max(error,Math.abs(dist(p.points[l.hip],p.points[l.knee])-l.upper),Math.abs(dist(p.points[l.knee],p.points[l.foot])-l.lower));}
 check('Pinned leg lengths remain intact '+n,error<1e-7);
 const disabled=F.create(run,jumps,{...settings,loadMs:0},m.parents,source,{time:0,surface,poseAt,velocityAt:()=>incoming});
 check('Load zero restores immediate push '+n,!disabled.bounce&&disabled.jumpStart===disabled.contactTime);
 const miss=F.create(run,jumps,settings,m.parents,source,{time:0,surface:S.rectangle('away',R.add(point,[20,0,0]),u,v,[-1,1,-1,1]),poseAt,velocityAt:()=>incoming});
 check('Miss gets no loading or launch '+n,!miss.bounce&&!Number.isFinite(miss.jumpStart));
}
// Fixed three-jump case with one-frame-earlier second marker; never alters saved state.
const cached=F.decodeNN(await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.61,drawn:true})})).json());
const setup={...C.defaults,runPhase:.61,supportCone:60,supportAlpha:6,supportSpeed:400,footRollSpeed:400,jumpEvents:[{id:'first',time:53/60,surface:'floor'},{id:'second',time:114/60,surface:'auto'},{id:'third',time:146/60,surface:'auto'}]};
const begin=performance.now(),sequence=F.sequence(cached,jumps,setup,m.parents),planMilliseconds=performance.now()-begin;
check('Closer first foot launches earlier; later unavailable contacts miss',sequence.segments[0].supportFoot==='L'&&sequence.events[0].status==='Push'&&sequence.events.slice(1).every(e=>e.status==='Miss'));
for(const segment of sequence.segments.filter(s=>s.bounce)){const t=segment.contactTime+segment.bounce.loadDuration/2,frame=sequence.sample(t),l=segment.support.leg;
 check('Repeated loading is visible '+segment.supportStart,frame.phase==='LOAD');
 check('Repeated loading follows the sole contact '+segment.supportStart,dist(frame.pose.points[l.foot],segment.contactMotion.sample(t-segment.contactTime).foot)<1e-5);
 check('Loading root matches sampled path '+segment.supportStart,dist(frame.root,segment.bounce.sample(t-segment.contactTime).p)<1e-8);
 check('Repeated bounce is deterministic '+segment.supportStart,JSON.stringify(sequence.sample(t))===JSON.stringify((sequence.sample(8),sequence.sample(0),sequence.sample(t))));
}
const late=F.sequence(cached,jumps,{...setup,jumpEvents:setup.jumpEvents.map((e,i)=>i===1?{...e,time:115/60}:e)},m.parents);
check('Original later marker cannot manufacture a push after changed arrival',late.events[1].status==='Miss'&&!late.segments[1].bounce&&late.segments[1].supportScores.every(s=>!s.eligible));
measurements.push({planMilliseconds,events:sequence.events});
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8');
check('Both controls appended after translucency',html.indexOf('id="loadMs"')>html.indexOf('id="platformTranslucency"')&&html.indexOf('id="rebound"')>html.indexOf('id="loadMs"')&&html.indexOf('id="rebound"')<html.indexOf('</details>'));
check('Options use existing preserve-playhead edit path',app.includes("['loadMs','rebound','jumpSkew'")&&app.includes("['supportTrigger','jumpSkew','rebound']"));
fs.writeFileSync(new URL('bounce-verification.json',import.meta.url),JSON.stringify({passed:true,browserVisualVerified:false,checks,measurements},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
