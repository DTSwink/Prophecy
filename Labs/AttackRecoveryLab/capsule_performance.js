  capsule(target, pointA, pointB, radius, color, segments = 18, hemisphereSteps = 6) {
    let axis = normalize(sub(pointB, pointA));
    if (norm(axis) < 1e-6) axis = [0, 1, 0];
    const reference = Math.abs(axis[1]) < .88 ? [0, 1, 0] : [1, 0, 0];
    const tangent = normalize(cross(axis, reference));
    const bitangent = normalize(cross(axis, tangent));
    const {coefficients:c,indices,vertices:v}=labCapsuleTemplate(segments,hemisphereSteps);
    for(let k=0,n=0;k<c.length;k+=5,n+=6){
      const center=c[k]?pointB:pointA,s=c[k+1],co=c[k+2],ct=c[k+3],st=c[k+4];
      let nx=axis[0]*s+(tangent[0]*ct+bitangent[0]*st)*co;
      let ny=axis[1]*s+(tangent[1]*ct+bitangent[1]*st)*co;
      let nz=axis[2]*s+(tangent[2]*ct+bitangent[2]*st)*co;
      const inv=1/(Math.hypot(nx,ny,nz)||1);nx*=inv;ny*=inv;nz*=inv;
      v[n]=center[0]+nx*radius;v[n+1]=center[1]+ny*radius;v[n+2]=center[2]+nz*radius;
      v[n+3]=nx;v[n+4]=ny;v[n+5]=nz;
    }
    for(let i=0;i<indices.length;i++){const n=indices[i]*6;target.push(v[n],v[n+1],v[n+2],v[n+3],v[n+4],v[n+5],color[0],color[1],color[2]);}
  }

