// node import_recorded_motion.cjs <RecordLocomotion.py output directory> [walk|run ...]
// Preserve the raw receipt; select a matching gait phase after at least 10s.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const R=require('./recovery.js');
const source=path.resolve(process.argv[2]),file=path.join(__dirname,'data/motions.json');
const data=JSON.parse(fs.readFileSync(file)),setup=require('./data/unreal-setup.json');
const previousHash=crypto.createHash('sha256').update(JSON.stringify([data,setup])).digest('hex');
for(const [from,to] of [[file,'motions-before.json'],[path.join(__dirname,'state.json'),'settings-before.json']])
 if(!fs.existsSync(path.join(source,to)))fs.copyFileSync(from,path.join(source,to));
function blend(a,b,u){return a.map((v,j)=>[...v.slice(0,3).map((x,k)=>x+(b[j][k]-x)*u),...R.qslerp(v.slice(3),b[j].slice(3),u)]);}
function errors(a,b){let position=0,rotation=0,cost=0;for(let j=1;j<a.length;j++){
 const p=R.length(R.sub(a[j].slice(0,3),b[j].slice(0,3))),q=2*Math.acos(Math.min(1,Math.abs(R.dot(a[j].slice(3),b[j].slice(3)))))*180/Math.PI;
 position=Math.max(position,p);rotation=Math.max(rotation,q);cost+=p*p+q*q*.04;
}return {position,rotation,cost};}
const receipt={};
const selected=process.argv.slice(3);if(selected.some(k=>!['walk','run'].includes(k)))throw Error('Expected walk or run');
for(const key of selected.length?selected:['walk','run']){
 const raw=JSON.parse(fs.readFileSync(path.join(source,key+'.json'))),rows=raw.rows;
 if(raw.reason!=='captured'||rows.length!==721||raw.fps!==60||rows[0].tick-raw.input_tick!==180)throw Error('Incomplete capture '+key);
 if(JSON.stringify(raw.names)!==JSON.stringify(data.names))throw Error('Skeleton mismatch');
 if(raw.checkpoint==='run'&&(raw.speed_scale!==1||raw.movement_input_length!==(key==='walk'?.4:1)||rows.some(r=>!r.running||!r.checkpoint_weights||r.checkpoint_weights[0]>1e-6||Math.abs(r.checkpoint_weights[1]-1)>1e-6)))throw Error('Incorrect run-checkpoint capture inputs/weights');
 rows.forEach((r,i)=>{if(r.tick!==rows[0].tick+i||r.pose.some(b=>b.some(x=>!Number.isFinite(x))))throw Error('Missing tick/nonfinite pose');});
 if(rows.some(r=>r.pose[1][2]<50||r.pose[1][2]>130))throw Error('Capture must use skeletal mesh origin, not capsule centre');
 const frames=rows.map(r=>r.pose),candidates=[];
 for(let start=0;start<=60;start++)for(let i=start+600;i<720;i++)candidates.push({start,index:i,...errors(frames[start],frames[i])});
 candidates.sort((a,b)=>a.cost-b.cost);
 let best={cost:Infinity};
 for(const candidate of candidates.slice(0,32)){
  const start=candidate.start,first=frames[start],i=candidate.index;
  let lo=0,hi=1;
  for(let n=0;n<28;n++){const a=lo+(hi-lo)/3,b=hi-(hi-lo)/3;
   if(errors(first,blend(frames[i],frames[i+1],a)).cost<errors(first,blend(frames[i],frames[i+1],b)).cost)hi=b;else lo=a;
  }
  const u=(lo+hi)/2,e=errors(first,blend(frames[i],frames[i+1],u));
  if(e.cost<best.cost)best={...e,start,index:i,u};
 }
 if(best.position>.2||best.rotation>1)throw Error('Recording has no clean loop: '+key+' '+JSON.stringify(best));
 const end=best.index+best.u;
 data.motions[key]={asset:'Unreal NN '+key+' forward · recorded 2026-10-12',fps:60,duration:(end-best.start)/60,
  recording:{source:raw.source,warmupTicks:180,inputTick:raw.input_tick,firstTick:rows[0].tick+best.start,captureFirstTick:rows[0].tick,capturedTicks:720,lastSourceTick:rows[0].tick+end,loopSeamCm:best.position,loopSeamDegrees:best.rotation},
  frames:[...frames.slice(best.start,best.index+1),blend(frames[best.index],frames[best.index+1],best.u)]};
 if(raw.checkpoint)data.motions[key].recording={...data.motions[key].recording,checkpoint:raw.checkpoint,movementInputLength:raw.movement_input_length,speedScale:raw.speed_scale};
 receipt[key]={...data.motions[key].recording,duration:data.motions[key].duration,frames:data.motions[key].frames.length};
}
data.previousSourceHashes=[...new Set([...(data.previousSourceHashes||[]),previousHash])];
fs.writeFileSync(file,JSON.stringify(data));
fs.writeFileSync(path.join(source,'import-receipt.json'),JSON.stringify(receipt,null,2));
console.log(JSON.stringify(receipt,null,2));
