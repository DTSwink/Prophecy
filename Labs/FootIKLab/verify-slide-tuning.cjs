'use strict';
// Isolated contact-particle checks: no NN, renderer, server, or user-state writes.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const R=require('./recovery.js'),K=require('./footik.js');
const {add,sub,mul,dot,length,unit}=R,DT=1/120;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
const tangent=(v,n)=>sub(v,mul(n,dot(v,n))),normal=[0,0,1];
const source=fs.readFileSync(path.join(__dirname,'surface.js'),'utf8');
const start=source.indexOf(' const hash=',source.indexOf('function createSlidePose'));
const end=source.indexOf(' const limitedRotation=',start);
assert(start>=0&&end>start,'Contact helper extraction boundary');
const make=input=>Function('R','s',`const {add,sub,mul,dot,length,unit}=R;const tangent=${tangent.toString()};const clamp=${clamp.toString()};const smooth=${smooth.toString()};${source.slice(start,end)};return {contactState,dragContact};`)(R,K.sanitize(input));

// Frozen pre-control integration, retained solely to verify defaults preserve
// the motion that was reviewed before these two controls were exposed.
const hash=x=>{const v=Math.sin(x*127.1+311.7)*43758.5453;return v-Math.floor(v);};
function priorStep(state,velocity,n,dt,active,amount=1){
 const carrier=tangent(velocity,n),speed=length(carrier);
 state.phase+=Math.min(speed,5)*dt/(3.1*(.7+.6*hash(Math.floor(state.phase)+71)));
 const cell=Math.floor(state.phase),f=state.phase-cell;
 const release=.40+.18*hash(cell+19),rough=(.55+.45*hash(cell))*smooth(f/.22)*(1-smooth((f-release)/(.94-release)));
 state.grip+=((active?rough:0)-state.grip)*(1-Math.exp(-dt*18));
 const frequency=9,stiffness=1+3*(length(state.x)/.20)**4,elastic=mul(state.x,-frequency*frequency*stiffness);
 const acceleration=sub(elastic,mul(state.v,2*1.05*frequency*Math.sqrt(stiffness))),freeVelocity=add(carrier,add(state.v,mul(acceleration,dt)));
 const friction=active?amount*(1.2+31*state.grip)*smooth(speed/.25):0;
 state.force=mul(unit(freeVelocity),-Math.min(friction,length(freeVelocity)/dt));
 state.v=tangent(add(state.v,mul(add(acceleration,state.force),dt)),n);state.x=tangent(add(state.x,mul(state.v,dt)),n);
}
const checks=[],check=(name,pass,details)=>{checks.push({name,passed:!!pass,...(details===undefined?{}:{details})});};
const defaults=K.sanitize();
check('Missing saved controls retain 100%',defaults.slideFriction===100&&defaults.slideRecovery===100);
for(const value of [null,'',Infinity,NaN]){const s=K.sanitize({slideFriction:value,slideRecovery:value});check('Invalid/blank controls use defaults '+String(value),s.slideFriction===100&&s.slideRecovery===100);}
const lo=K.sanitize({slideFriction:-1,slideRecovery:0}),hi=K.sanitize({slideFriction:999,slideRecovery:999});
check('Controls sanitize to supported bounds',lo.slideFriction===0&&lo.slideRecovery===10&&hi.slideFriction===300&&hi.slideRecovery===200);
let identical=true;
for(const amount of [1,.8]){const api=make({}),a=api.contactState(2.21),b=structuredClone(a);for(let i=0;i<1200;i++){api.dragContact(a,[0,-25,0],normal,DT,i<600,amount);priorStep(b,[0,-25,0],normal,DT,i<600,amount);identical&&=JSON.stringify(a)===JSON.stringify(b);}}
check('100% controls preserve prior particle motion exactly',identical);

function release(recovery,distance=.15){
 const api=make({slideRecovery:recovery}),state=api.contactState(2.21);state.x=[0,distance,0];let return80=null,peak=0,firstSpeed;
 for(let i=0;i<2400;i++){api.dragContact(state,[0,0,0],normal,DT,false);const v=length(state.v);if(i===0)firstSpeed=v;peak=Math.max(peak,v);if(return80===null&&length(state.x)<=distance*.2)return80=(i+1)*DT;}
 return {recovery,distance,return80,peak,firstSpeed,finalDistance:length(state.x)};
}
const releases=[10,25,100,200].map(v=>release(v));
check('Lower recovery gives slower matched-distance return',releases.every((r,i)=>r.return80!==null&&(!i||r.return80<releases[i-1].return80)),releases);
check('Lower recovery reduces matched-release peak speed',releases.every((r,i)=>!i||r.peak>releases[i-1].peak),releases);
const near=release(100,.05),far=release(100,.15);
check('Farther displacement starts with a stronger pull',far.firstSpeed>near.firstSpeed*3,{near,far});

const grid=[];
for(const friction of [0,100,300])for(const recovery of [10,25,100,200]){
 const api=make({slideFriction:friction,slideRecovery:recovery}),state=api.contactState(2.21);let peakInward=0,maxOffset=0,finite=true,maxNormal=0;
 for(let i=0;i<1200;i++){
  api.dragContact(state,[0,-25,0],normal,DT,i<600);
  finite&&=[...state.x,...state.v,...state.force].every(Number.isFinite);maxOffset=Math.max(maxOffset,length(state.x));maxNormal=Math.max(maxNormal,Math.abs(dot(state.x,normal)),Math.abs(dot(state.v,normal)));
  if(dot(state.x,state.v)<0)peakInward=Math.max(peakInward,-dot(state.v,unit(state.x)));
 }
 grid.push({friction,recovery,peakInward,maxOffset,finite,maxNormal});
}
check('Entire friction/recovery grid stays finite and tangent',grid.every(r=>r.finite&&r.maxNormal<1e-12&&r.maxOffset<1),grid);
check('Zero friction creates no contact displacement',grid.filter(r=>r.friction===0).every(r=>r.maxOffset===0));
for(const friction of [100,300]){const rows=grid.filter(r=>r.friction===friction);check(friction+'% friction: lower recovery slows actual rough-patch returns',rows.every((r,i)=>!i||r.peakInward>rows[i-1].peakInward),rows);}
const firstForce=[];for(const friction of [0,100,300]){const api=make({slideFriction:friction}),state=api.contactState(2.21);api.dragContact(state,[0,-25,0],normal,DT,true);firstForce.push(length(state.force));}
check('Friction strength scales catch force independently',firstForce[0]===0&&Math.abs(firstForce[2]-3*firstForce[1])<1e-12,firstForce);
const report={passed:checks.every(c=>c.passed),sampleHz:120,checks,releases,grid,notes:'Recovery force remains distance-based with the existing progressive stretch guard. Lower speed adds damping; no fixed-speed return cap. Grid is a particle stress test, not full-body motion validation.'};
fs.writeFileSync(path.join(__dirname,'snapshots/slide-tuning-verification.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({passed:report.passed,checks:checks.length,failed:checks.filter(c=>!c.passed),releases,grid}));
if(!report.passed)process.exitCode=1;
