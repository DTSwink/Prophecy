'use strict';
// Same scalar operation order and corner order as support.js. No intermediate
// vector arrays/flatMap callbacks are needed for the three independent axes.
function corners(c,f,s,u,d){
 const out=[];
 for(const x of [-1,1]){
  const fx=x*d[0]/2,a=c[0]+f[0]*fx,b=c[1]+f[1]*fx,e=c[2]+f[2]*fx;
  for(const y of [-1,1]){
   const sy=y*d[1]/2,g=a+s[0]*sy,h=b+s[1]*sy,j=e+s[2]*sy;
   for(const z of [-1,1]){const uz=z*d[2]/2;out.push([g+u[0]*uz,h+u[1]*uz,j+u[2]*uz]);}
  }
 }
 return out;
}
module.exports={corners};
