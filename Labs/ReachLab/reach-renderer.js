// Shared by the visible canvas and the D/S-derived capture worker.
class ReachRenderer extends WebGLMotionRenderer {
 draw(data,sharedRoot){
  super.draw(data,sharedRoot);if(!data)return;
  // Contact references share scene depth so nearer geometry occludes them.
  const mesh=this.contactStream||(this.contactStream=new LabVertexStream(8192));mesh.length=0;
  for(let k=0;k<2;k++){
   const contact=data.contacts?.[k];
   if(contact){
    const n=normalize(contact.normal),tip=add(contact.point,mul(n,.055)),base=add(tip,mul(n,-.012)),gold=[1,.76,.12];
    let tangent=normalize(cross(n,[0,1,0]));if(norm(tangent)<1e-7)tangent=normalize(cross(n,[1,0,0]));
    this.capsule(mesh,contact.point,tip,.0018,gold,8,3);
    for(const sign of [-1,1])this.capsule(mesh,tip,add(base,mul(tangent,sign*.006)),.0018,gold,8,3);
    this.capsule(mesh,contact.point,contact.point,.005,[1,.82,.2],12,6);
    if(contact.actual){
     this.capsule(mesh,contact.actual,contact.actual,.0035,[.2,1,1],10,4);
     this.capsule(mesh,contact.actual,contact.point,.0008,[.2,1,1],6,2);
    }
   }
  }
  const gl=this.gl;gl.enable(gl.DEPTH_TEST);gl.depthMask(true);
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);
 }
 handBox(data,spec){return data.palms?.[spec.side===1?1:0]||super.handBox(data,spec);}
 addBody(mesh,data){
  super.addBody(mesh,data);
  for(let k=0;k<2;k++){
   const h=data.targets[k],p=h.point,color=h.enabled?(k===0?[.25,.85,.96]:[.97,.45,.76]):[.35,.4,.44],w=data.points[k===0?13:17];
   this.capsule(mesh,p,p,h.radius||.03,color,24,10);this.groundRing(mesh,[p[0],.004,p[2]],.035,.045,color);
   for(const segment of data.fingerLines?.[k]||[])this.capsule(mesh,segment.a,segment.b,.0065,[.78,.85,.87],10,4);
   if(h.gripped){this.groundRing(mesh,[p[0],.005,p[2]],.05,.055,[.75,1,.3]);if(Math.hypot(...h.goal.map((v,i)=>v-p[i]))>.01)this.capsule(mesh,p,h.goal,.0015,[.75,1,.3],6,2);}
   if(h.enabled)this.capsule(mesh,w,p,.0025,color,6,2);
   if(data.showWristAxes)for(let i=0;i<3;i++)this.controllerAxis(mesh,w,data.wristDirections[k][i],[[1,.25,.2],[.2,.95,.35],[.25,.5,1]][i],.11);
  }
 }
}
