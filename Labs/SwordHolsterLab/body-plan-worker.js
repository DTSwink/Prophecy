// Full trajectories are preparation work; keep them off the interactive thread.
importScripts('recovery.js','bodyreach.js','armfk.js','retime.js','headlook.js','fkreturn.js','elbowpole.js','holster.js');
const assets=Promise.all(['data/motions.json','data/unreal-setup.json'].map(url=>fetch(url).then(r=>r.json())));
onmessage=async({data:{version,options}})=>{
 try{
  const [data,setup]=await assets,model=Holster.prepare(data,setup,options);
  // The main thread already owns the unchanged source assets.
  delete model.data;delete model.setup;
  postMessage({version,model});
 }catch(error){postMessage({version,error:String(error.stack||error)});}
};
