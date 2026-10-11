// Reuse the recovery lab's renderer; supply the real exported equipment meshes.
class HolsterRenderer extends WebGLMotionRenderer {
 addSword(stream,data){
  if(!data.equipment||data.hideSword)return;
  this.equipmentPoints ||= new WeakMap();
  for(const [key,color] of [['holster',[.13,.64,.58]],['sword',[.83,.87,.91]]]){
   const item=data.equipment[key],geometry=equipmentSetup[key+'Mesh'];
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
