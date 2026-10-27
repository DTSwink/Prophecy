'use strict';
document.getElementById('refresh').onclick=()=>location.reload();
// The small existing loopback server has a limited connection backlog. Load
// dependencies in order instead of opening a burst of connections on Refresh.
(async()=>{
 for(const src of ['recovery.js','geometry.js','camera.js','renderer.js','scenes.js','vanilla.js','core.js','gizmos.js','history.js','app.js']){
  await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=()=>reject(Error('Could not load '+src+'. Press Refresh to retry.'));document.body.append(script);});
 }
})().catch(error=>{const el=document.getElementById('error');el.textContent=error.message;el.hidden=false;});
