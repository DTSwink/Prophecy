// Reuse the recovery lab's renderer; supply the real exported equipment meshes.
class HolsterRenderer extends WebGLMotionRenderer {
 draw(data,sharedRoot){
  super.draw(data,sharedRoot);
  if(data?.pelvisDistance){
   const gl=this.gl,d=data.pelvisDistance,lines=this.distanceLines||(this.distanceLines=new LabVertexStream(64)),mesh=this.distanceMesh||(this.distanceMesh=new LabVertexStream(8192));
   lines.length=0;mesh.length=0;
   const a=displayPoint(d.holster,data.shift),b=displayPoint(d.pelvis,data.shift),color=[1,.85,.2];
   this.line(lines,a,b,color);
   for(const p of [a,b])this.capsule(mesh,p,p,.004,color,8,3);
   gl.disable(gl.DEPTH_TEST);gl.uniform1i(this.locations.unlit,1);
   this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
   gl.uniform1i(this.locations.unlit,0);gl.enable(gl.DEPTH_TEST);
  }
  if(!data?.leeway)return;
  const gl=this.gl,debug=data.leeway,lines=this.leewayLines||(this.leewayLines=new LabVertexStream(8192)),mesh=this.leewayMesh||(this.leewayMesh=new LabVertexStream(32768));
  lines.length=0;mesh.length=0;
  for(const segment of debug.lines){
   const a=displayPoint(segment.a,data.shift),b=displayPoint(segment.b,data.shift),color=segment.color.map(x=>x/255);
   if(segment.width>1)this.capsule(mesh,a,b,segment.width*.0006,color,6,2);
   else this.line(lines,a,b,color);
  }
  const tip=displayPoint(debug.tip,data.shift);
  this.capsule(mesh,tip,tip,.006,debug.tipColor.map(x=>x/255),10,3);
  // UE debug uses foreground depth: keep the allowance visible through the equipment.
  gl.disable(gl.DEPTH_TEST);gl.uniform1i(this.locations.unlit,1);
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
  gl.uniform1i(this.locations.unlit,0);gl.enable(gl.DEPTH_TEST);
 }

 addSword(stream,data){
  if(!data.equipment||data.hideSword)return;
  this.equipmentPoints ||= new WeakMap();
  for(const [key,color] of [['holster',[.13,.64,.58]],['sword',[.83,.87,.91]]]){
   const item=data.equipment[key],geometry=data.equipment[key+'Mesh']||equipmentSetup[key+'Mesh'];
   const axes=Recovery.toAxes(item.q).map((v,j)=>v.map(x=>x*item.s[j]/100));
   const origin=displayPoint(item.p,data.shift);
   for(const section of geometry.sections){
    let points=this.equipmentPoints.get(section);
    if(!points){points=new Float64Array(section.vertices.length*3);this.equipmentPoints.set(section,points);}
    for(let j=0;j<section.vertices.length;j++){
     const p=section.vertices[j],n=j*3;
     points[n]=origin[0]+axes[0][0]*p[0]+axes[1][0]*p[1]+axes[2][0]*p[2];
     points[n+1]=origin[1]+axes[0][2]*p[0]+axes[1][2]*p[1]+axes[2][2]*p[2];
     points[n+2]=origin[2]+axes[0][1]*p[0]+axes[1][1]*p[1]+axes[2][1]*p[2];
    }
    for(let i=0;i<section.triangles.length;i+=3){
     const a=section.triangles[i]*3,b=section.triangles[i+1]*3,c=section.triangles[i+2]*3;
     const ux=points[b]-points[a],uy=points[b+1]-points[a+1],uz=points[b+2]-points[a+2],vx=points[c]-points[a],vy=points[c+1]-points[a+1],vz=points[c+2]-points[a+2];
     const nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx,inv=1/(Math.hypot(nx,ny,nz)||1);
     for(const n of [a,b,c])stream.push(points[n],points[n+1],points[n+2],nx*inv,ny*inv,nz*inv,color[0],color[1],color[2]);
    }
   }
  }
 }
}
