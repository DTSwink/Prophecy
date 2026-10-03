// Reusable vertex storage; geometry, tessellation and draw order stay unchanged.
class LabVertexStream {
  constructor(capacity){this.data=new Float32Array(capacity);this.length=0;}
  push(a,b,c,d,e,f,g,h,i){
    const end=this.length+9;
    if(end>this.data.length){const next=new Float32Array(Math.max(end,this.data.length*2));next.set(this.data);this.data=next;}
    const v=this.data,n=this.length;v[n]=a;v[n+1]=b;v[n+2]=c;v[n+3]=d;v[n+4]=e;v[n+5]=f;v[n+6]=g;v[n+7]=h;v[n+8]=i;this.length=end;
  }
  view(){return this.data.subarray(0,this.length);}
}
const labCapsuleTemplates=new Map();
function labCapsuleTemplate(segments,steps){
 const key=segments+':'+steps;if(labCapsuleTemplates.has(key))return labCapsuleTemplates.get(key);
 const coefficients=[],indices=[];
 const ring=(end,phi)=>{for(let j=0;j<segments;j++){const theta=j*Math.PI*2/segments;coefficients.push(end,Math.sin(phi),Math.cos(phi),Math.cos(theta),Math.sin(theta));}};
 for(let i=0;i<=steps;i++)ring(0,-Math.PI*.5+Math.PI*.5*i/steps);
 ring(1,0);for(let i=1;i<=steps;i++)ring(1,Math.PI*.5*i/steps);
 for(let i=0;i<2*steps+1;i++)for(let j=0;j<segments;j++){const next=(j+1)%segments,a=i*segments+j,b=(i+1)*segments+j,c=(i+1)*segments+next,d=i*segments+next;indices.push(a,b,c,a,c,d);}
 const template={coefficients:new Float64Array(coefficients),indices:new Uint32Array(indices),vertices:new Float64Array(coefficients.length/5*6)};
 labCapsuleTemplates.set(key,template);return template;
}
