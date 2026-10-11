// Re-render the frozen displayed pose in a worker. No GPU readback or PNG
// encoding touches the playback thread; capture never evaluates motion.
class LabFrameCapture {
 constructor(canvas,setup){
  this.canvas=canvas;this.serial=0;this.pending=new Map();
  if(typeof OffscreenCanvas!=='undefined'){
   this.worker=new Worker('capture-worker.js');
   this.worker.postMessage({setup});
   this.worker.onmessage=({data})=>{const job=this.pending.get(data.id);if(!job)return;this.pending.delete(data.id);data.error?job.reject(Error(data.error)):job.resolve(data.image);};
   this.worker.onerror=e=>{for(const job of this.pending.values())job.reject(Error(e.message));this.pending.clear();this.worker.terminate();this.worker=null;};
  }
 }
 png(frame){
  if(!this.worker)return new Promise((resolve,reject)=>this.canvas.toBlob(blob=>{if(!blob)return reject(Error('Capture failed'));const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(blob);},'image/png'));
  const viewKey=JSON.stringify([frame.camera,frame.rect,frame.pixelRatio]);
  if(this.last?.pose===frame.pose&&this.last.viewKey===viewKey)return this.last.image;
  const id=++this.serial;
  const image=new Promise((resolve,reject)=>{this.pending.set(id,{resolve,reject});this.worker.postMessage({id,frame});});
  const entry=this.last={pose:frame.pose,viewKey,image};
  image.catch(()=>{if(this.last===entry)this.last=null;});
  return image;
 }
}
