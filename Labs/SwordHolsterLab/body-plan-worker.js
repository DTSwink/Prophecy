// Full trajectories are preparation work; keep them off the interactive thread.
// Use the worker's content revision so a rollback cannot reuse newer cached scripts.
const revision=new URL(self.location.href).search;
importScripts(...['recovery.js','bodyreach.js','armfk.js','retime.js','headlook.js','fkreturn.js','elbowpole.js','tipalign.js','online.js','holster.js','sequence.js'].map(file=>file+revision));
const assets=Promise.all(['data/motions.json','data/unreal-setup.json'].map(url=>fetch(url).then(r=>r.json())));
onmessage=async({data:{version,options}})=>{
 try{
  const [data,setup]=await assets,model=HolsterPlayback.prepare(data,setup,options);
  // The main thread already owns the unchanged source assets.
  HolsterPlayback.assets(model);
  postMessage({version,model});
 }catch(error){postMessage({version,error:String(error.stack||error)});}
};
