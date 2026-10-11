// Same renderer, tessellation and camera as the viewport, on its own thread.
importScripts('recovery.js','renderer.js','equipment.js');
const {add,sub,mul,dot,cross,length:norm,unit:normalize}=Recovery;
const posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
function displayPoint(p,shift=[0,0,0]){return [(p[0]-shift[0])/100,(p[2]-shift[2])/100,(p[1]-shift[1])/100];}
let parents,nameToIndex,equipmentSetup,cameraState,renderer;
async function encodeFrame(){
 const gl=renderer.gl,{width,height}=renderer.canvas,pixels=new Uint8ClampedArray(width*height*4);
 // convertToBlob on a WebGL canvas synchronously drains the shared GPU queue.
 // Queue the read, wait without blocking, and encode a CPU-backed 2D image.
 if(gl.fenceSync){
  const buffer=gl.createBuffer();let fence;
  try{
   gl.bindBuffer(gl.PIXEL_PACK_BUFFER,buffer);gl.bufferData(gl.PIXEL_PACK_BUFFER,pixels.byteLength,gl.STREAM_READ);
   gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,0);fence=gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE,0);gl.flush();gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
   const deadline=performance.now()+10000;
   for(;;){const status=gl.clientWaitSync(fence,0,0);if(status===gl.ALREADY_SIGNALED||status===gl.CONDITION_SATISFIED)break;if(status===gl.WAIT_FAILED||gl.isContextLost()||performance.now()>deadline)throw Error('Capture GPU read failed');await new Promise(r=>setTimeout(r,8));}
   gl.bindBuffer(gl.PIXEL_PACK_BUFFER,buffer);gl.getBufferSubData(gl.PIXEL_PACK_BUFFER,0,pixels);
  }finally{gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);if(fence)gl.deleteSync(fence);gl.deleteBuffer(buffer);}
 }else gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
 const stride=width*4,row=new Uint8ClampedArray(stride);
 for(let y=0;y<Math.floor(height/2);y++){const a=y*stride,b=(height-1-y)*stride;row.set(pixels.subarray(a,a+stride));pixels.copyWithin(a,b,b+stride);pixels.set(row,b);}
 const canvas=new OffscreenCanvas(width,height);
 canvas.getContext('2d',{willReadFrequently:true}).putImageData(new ImageData(pixels,width,height),0,0);
 return canvas.convertToBlob({type:'image/png'});
}
self.onmessage=async({data})=>{
 const {id,frame,setup}=data;
 if(setup){parents=setup.parents;nameToIndex=new Map(setup.names.map((n,i)=>[n,i]));equipmentSetup=setup.equipment;return;}
 try{
  cameraState=frame.camera;
  if(!renderer)renderer=new HolsterRenderer(new OffscreenCanvas(1,1),{interactive:false,rect:frame.rect,pixelRatio:frame.pixelRatio});
  renderer.rect=frame.rect;renderer.pixelRatio=frame.pixelRatio;
  renderer.draw(frame.pose,[0,0,0]);
  const blob=await encodeFrame();
  self.postMessage({id,image:new FileReaderSync().readAsDataURL(blob)});
 }catch(e){self.postMessage({id,error:String(e)});}
};
