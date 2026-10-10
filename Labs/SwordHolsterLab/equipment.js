// Reuse the recovery lab's renderer; supply the real exported equipment meshes.
class HolsterRenderer extends WebGLMotionRenderer {
 addSword(stream,data){
  if(!data.equipment||data.hideSword)return;
  for(const [key,color] of [['holster',[.13,.64,.58]],['sword',[.83,.87,.91]]]){
   const item=data.equipment[key],geometry=equipmentSetup[key+'Mesh'];
   for(const section of geometry.sections){
    const points=section.vertices.map(p=>displayPoint(Recovery.add(item.p,Recovery.rotate(item.q,p.map((x,i)=>x*item.s[i]))),data.shift));
    for(let i=0;i<section.triangles.length;i+=3){
     const [a,b,c]=section.triangles.slice(i,i+3).map(j=>points[j]);
     this.triangle(stream,a,b,c,normalize(cross(sub(b,a),sub(c,a))),color);
    }
   }
  }
 }
}
