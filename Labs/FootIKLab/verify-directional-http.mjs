// HTTP contract audit against the isolated FootIK server. One serial request at
// a time; server owns its lazy CPU worker and retirement. No process control.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js');
const endpoint=process.env.FOOTIK_DIRECTION_TEST_URL||'http://127.0.0.1:8890';
const rig=JSON.parse(fs.readFileSync(new URL('./data/rig.json',import.meta.url)));
const checks=[],cases=[],phases=[],started=Date.now();
const check=(name,value)=>{assert(value,name);checks.push(name);};
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
async function post(path,request){
 const response=await fetch(endpoint+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(60000)});
 const data=await response.json();if(!response.ok)throw Error(data.error||`HTTP${response.status}`);return data;
}
const health=await(await fetch(endpoint+'/health')).json();
check('isolated FootIK API6',health.app==='foot-ik-lab'&&health.apiVersion===6);
const fixture=(gait,direction)=>JSON.parse(fs.readFileSync(new URL(`.nn-cache/directional-${gait}-${direction}.json`,import.meta.url)));
for(const gait of ['walk','run'])for(const direction of ['backward','left','right']){
 const source=fixture(gait,direction),current=41,count=12;
 // Translate the whole rig to an elevated surface and give corrected current
 // pelvis/body a different lateral offset from previous. Bone geometry remains
 // unchanged; both actual history samples differ from the cached source.
 const roots=source.roots.slice(current-1,current+count+8).map(p=>R.add(p,[0,.35,0]));
 const seeds=[current-1,current].map((i,j)=>({
  points:[roots[j],...source.poses[i].points.map(p=>R.add(p,[j?.020:.015,.35,0]))],
  axes:[[[1,0,0],[0,1,0],[0,0,1]],...source.poses[i].axes]
 }));
 const request={gait,direction,frames:count,roots,seeds,names:['root',...source.names],verifyReference:true};
 const begin=Date.now(),data=await post('/resume',request),prefix=`${gait}/${direction} `;
 check(prefix+'both original controllers verified',data.referenceError===0&&data.inferences===count-1&&data.fps===30);
 check(prefix+'exact corrected current seed',equal(data.poses[0],{points:seeds[1].points.slice(1),axes:seeds[1].axes.slice(1)}));
 check(prefix+'both corrected history samples encoded',data.seedLower.length===2&&data.seedUpper.length===2&&!equal(data.seedLower[0],data.seedLower[1]));
 check(prefix+'course root path preserved exactly',equal(data.roots,roots.slice(1,count+1)));
 check(prefix+'directional source context retained',data.direction===direction&&data.command.direction===direction&&data.command.relative===source.command.relative);
 const speed=R.length(R.sub(data.roots.at(-1),data.roots[0]))/((data.roots.length-1)/30);
 check(prefix+'native root speed',Math.abs(speed-source.command.commandSpeed)<.001);
 const desired=direction==='backward'?[0,0,-1]:direction==='left'?[-1,0,0]:[1,0,0];
 const head=source.names.indexOf('head'),cosines=data.poses.map(p=>{const f=R.mul(p.axes[head][1],-1);f[1]=0;return R.dot(R.unit(f),desired);});
 check(prefix+'rendered head facing retained',Math.min(...cosines)>.9);
 check(prefix+'finite full body continuation',data.poses.length===count&&data.poses.every(p=>p.points.flat().every(Number.isFinite)&&p.axes.flat(2).every(Number.isFinite)));
 const repeated=await post('/resume',request);
 check(prefix+'identical request uses cache',repeated.cache==='identical-seed'&&equal(repeated.poses,data.poses));
 if(gait==='walk'&&direction==='backward'){
  const altered=structuredClone(request);altered.seeds[0].points.slice(1).forEach(p=>p[0]+=.003);
  const second=await post('/resume',altered);
  const change=Math.max(...second.poses[1].points.flat().map((v,i)=>Math.abs(v-data.poses[1].points.flat()[i])));
  check(prefix+'actual prediction depends on previous corrected history',change>1e-6);
 }
 const row={gait,direction,referenceError:data.referenceError,speed,minHeadFacingCosine:Math.min(...cosines),seconds:(Date.now()-begin)/1000,initialCache:data.cache};cases.push(row);console.log(JSON.stringify(row));
}
for(const [gait,direction,phase] of [['walk','backward',0],['run','left',.49],['run','right',.73]]){
 const begin=Date.now(),data=await post('/run',{gait,direction,duration:1.5,phase}),source=fixture(gait,direction),run=K.decode(data,rig.parents);
 const model=K.prepare(run,{...K.defaults,gait,direction,phase,terrain:'flat'}),prefix=`${gait}/${direction}/phase${phase} `;
 check(prefix+'genuine direction metadata and recurrence',data.direction===direction&&data.lowerInferences>60&&data.upperInferences>30&&data.source.includes('autoregressive'));
 let positionError=0,rotationError=0;
 for(const f of model.frames)for(let i=0;i<run.names.length;i++){
  positionError=Math.max(positionError,R.length(R.sub(f.pose.points[i],f.raw.points[i])));
  rotationError=Math.max(rotationError,1-Math.abs(R.dot(f.pose.q[i],f.raw.q[i])));
 }
 check(prefix+'flat remains exact NN',positionError<1e-8&&rotationError<1e-12);
 const shift=data.sourceStartFrame-source.sourceStartFrame,a=Math.max(0,-shift),b=a+shift;
 const feet=['foot_l','foot_r','ball_l','ball_r'].map(n=>data.names.indexOf(n));
 const phaseError=Math.max(...feet.map(j=>R.length(R.sub(R.sub(data.poses[a].points[j],data.roots[a]),R.sub(source.poses[b].points[j],source.roots[b])))));
 check(prefix+'phase only selects starting position in same NN gait',phaseError<2e-5);
 const desired=direction==='backward'?[0,0,-1]:direction==='left'?[-1,0,0]:[1,0,0],head=data.names.indexOf('head');
 const facing=data.poses.map(p=>{const f=R.mul(p.axes[head][1],-1);f[1]=0;return R.dot(R.unit(f),desired);});
 check(prefix+'body remains backward/lateral',Math.min(...facing)>.9);
 const repeated=await post('/run',{gait,direction,duration:1.5,phase});
 check(prefix+'generated phase cache is exact',repeated.cache==='identical-seed'&&equal(repeated.poses,data.poses));
 const row={gait,direction,phase,phaseError,maxFlatPositionError:positionError,minHeadFacingCosine:Math.min(...facing),seconds:(Date.now()-begin)/1000};phases.push(row);console.log(JSON.stringify(row));
}
const receipt={endpoint,health,count:checks.length,checks,cases,phases,seconds:(Date.now()-started)/1000};
fs.writeFileSync(new URL('./directional-http-verification.json',import.meta.url),JSON.stringify(receipt,null,2));
console.log(JSON.stringify({passed:checks.length,seconds:receipt.seconds}));
