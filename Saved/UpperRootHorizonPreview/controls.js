window.upperHorizonBenchPaused=false;
const horizonSlider=document.getElementById('horizonSlider');
const horizonStatus=document.getElementById('horizonStatus');
let horizonRequest=0;
let horizonAbort=null;

async function horizonFetch(path) {
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),12000);
 try {return await (await originalFetch('http://127.0.0.1:8033'+path,{signal:controller.signal,cache:'no-store'})).json();}
 finally {clearTimeout(timer);}
}
async function pollHorizonBenchmark() {
 try {const status=await horizonFetch('/health');window.upperHorizonBenchPaused=status.benchmark_running;}catch(error){}
}
pollHorizonBenchmark();setInterval(pollHorizonBenchmark,2000);

async function applyUpperHorizon(factor) {
 const request=++horizonRequest;
 horizonStatus.textContent='Requesting upper NN replay…';
 const started=performance.now();
 try {
  while(request===horizonRequest) {
   const data=await horizonFetch('/rollout?factor='+factor);
   if(request!==horizonRequest)return;
   if(data.error)throw new Error(data.error);
   if(data.waiting) {
    horizonStatus.textContent=data.message+' · '+Math.round((performance.now()-started)/1000)+' s. Still showing '+Number(payload?.metadata?.upper_rotation_horizon??1).toFixed(2)+' until ready.';
    await new Promise(resolve=>setTimeout(resolve,1000));
    continue;
   }
   if(!data.positions||!data.upper_root_window_positions)throw new Error('Replay is missing its root window');
   const oldRow=row,wasPlaying=playing;
   payload=data;row=oldRow;frame=0;subframe=0;frameCarry=0;
   updateOverlayAvailability();updateRowSelect();setPlaying(wasPlaying);
   horizonStatus.textContent='Showing '+factor.toFixed(2)+' · upper NN replay and its exact root window.';
   return;
  }
 } catch(error) {
  if(request===horizonRequest)horizonStatus.textContent='Replay failed: '+(error.name==='AbortError'?'helper timed out. Use Retry.':error.message);
 }
}
horizonSlider.addEventListener('input',()=>{document.getElementById('horizonValue').textContent=Number(horizonSlider.value).toFixed(2);});
horizonSlider.addEventListener('change',()=>applyUpperHorizon(Number(horizonSlider.value)));
document.getElementById('horizonRetry').addEventListener('click',()=>applyUpperHorizon(Number(horizonSlider.value)));

// Replace the legacy current/frozen/target root references only in this page.
drawRootReferences=function() {
 const positions=framePayload('upper_root_window_positions');
 const forwards=framePayload('upper_root_window_forwards');
 if(!positions||!forwards)return;
 window.upperRootWindowDrawn=positions.length;
 for(let i=1;i<positions.length;i++)drawSegment3d(positions[i-1],positions[i],'#4d879a',1.1);
 for(let i=positions.length-1;i>=0;i--) {
  const color=i===0?'#ffffff':`hsl(${165+i*18},90%,65%)`;
  const origin=positions[i],forward=forwards[i],length=i===0?0.27:0.36+i*0.105;
  drawPointAndForward(origin,forward,color,i===0?5:3,length);
  const tip=add(toViewerPoint(origin),mul(normalize(toViewerPoint(forward)),length+0.04));
  const point=project(tip);
  if(point&&point.z>0.08) {
   ctx.save();ctx.font='bold 12px Segoe UI';ctx.lineWidth=3;ctx.strokeStyle='#10151b';ctx.fillStyle=color;
   ctx.strokeText('R'+i,point.x+4,point.y-3);ctx.fillText('R'+i,point.x+4,point.y-3);ctx.restore();
  }
 }
};

// Wait for the original player to initialize, then load its window without changing the default.
const initialWindow=setInterval(()=>{
 if(typeof payload!=='undefined'&&payload?.positions?.length){clearInterval(initialWindow);horizonStatus.textContent='Showing 1.00 · upper NN replay and its exact root window.';}
},100);
