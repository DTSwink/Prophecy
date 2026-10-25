'use strict';
// Opt-in, bounded GPU check; never loaded by the app or launcher.
const {add,sub,mul,dot,cross,length:norm,unit:normalize}=Recovery;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(p,j)=>p.points[j],axisAt=(p,j,a)=>p.axes[j][a];
const cameraState={yaw:1.05,pitch:.08,zoom:.8,panX:0,panY:0};
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null;
function drawAll(){}
document.getElementById('check').onclick=async()=>{
 const button=document.getElementById('check'),result=document.getElementById('result');button.disabled=true;
 let renderer;
 try{
  const [rig,fixture]=await Promise.all(['data/rig.json','data/walk-fixture.json'].map(p=>fetch(p).then(r=>r.json())));
  names=rig.names;parents=rig.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));
  const run=FootIK.decode(fixture,parents),model=FootIK.prepare(run,FootIK.sanitize());
  renderer=new WebGLMotionRenderer(document.getElementById('canvas'),{interactive:false,pixelRatio:1});
  const gl=renderer.gl,ext=gl.getExtension('EXT_disjoint_timer_query_webgl2'),queries=[],cpu=[],checks=[];
  const check=(label,ok)=>{if(!ok)throw Error(label);checks.push(label);};
  const draw=t=>{const pose=model.sample(t).pose;renderer.draw({...pose,hideSword:true,voidScene:true,bicolor:true,skeleton:false},BodyflipSupport.com(pose,names,parents,run.poses[0]));};
  draw(0); // Shader/driver warmup excluded.
  const update=renderer.updateShadow.bind(renderer);
  renderer.updateShadow=function(...args){
   const query=ext?gl.createQuery():null;
   if(query)gl.beginQuery(ext.TIME_ELAPSED_EXT,query);
   const before=performance.now();update(...args);cpu.push(performance.now()-before);
   if(query){gl.endQuery(ext.TIME_ELAPSED_EXT);queries.push(query);}
  };
  for(let i=1;i<=32;i++){await new Promise(requestAnimationFrame);draw(i/15);}
  renderer.updateShadow=update;
  check('One depth draw per changed pose',renderer.shadow.renders===33);
  const renders=renderer.shadow.renders;
  cameraState.yaw+=.3;draw(32/15);draw(32/15);
  check('Camera-only redraws reuse the shadow map',renderer.shadow.renders===renders);
  const glError=gl.getError();check('No WebGL errors',glError===gl.NO_ERROR);
  const gpu=[];const deadline=performance.now()+3000;
  while(queries.length&&performance.now()<deadline){
   await new Promise(requestAnimationFrame);
   if(gl.getParameter(ext.GPU_DISJOINT_EXT))break;
   while(queries.length&&gl.getQueryParameter(queries[0],gl.QUERY_RESULT_AVAILABLE)){
    const q=queries.shift();gpu.push(gl.getQueryParameter(q,gl.QUERY_RESULT)/1e6);gl.deleteQuery(q);
   }
  }
  for(const q of queries)gl.deleteQuery(q);
  const stats=v=>{if(!v.length)return null;v.sort((a,b)=>a-b);return {samples:v.length,medianMs:v[Math.floor(v.length*.5)],p95Ms:v[Math.min(v.length-1,Math.floor(v.length*.95))]};};
  result.textContent=JSON.stringify({checks,shadow:{resolution:1024,depthMiB:4,triangles:renderer.meshStream.length/27,
   cpuSubmission:stats(cpu),gpu:stats(gpu),timerAvailable:!!ext},note:'GPU timer covers the extra shadow pass. It is not total application frame time.'},null,2);
 }catch(e){result.textContent='FAIL: '+e.stack;}
 finally{button.disabled=false;renderer?.gl.getExtension('WEBGL_lose_context')?.loseContext();}
};
