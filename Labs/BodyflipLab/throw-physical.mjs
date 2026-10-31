// Export the same scaled Jolt shape mass frame; no physics world or stepping.
import initJolt from './vendor/jolt.mjs';
import R from './recovery.js';
export async function physicalAssets(data){
 const J=await initJolt(),owned=[],arr=v=>[v.GetX(),v.GetY(),v.GetZ()],result={};
 function diagonalize(columns){
  const a=columns.map((_,i)=>columns.map(c=>c[i])),v=[[1,0,0],[0,1,0],[0,0,1]];
  for(let n=0;n<32;n++){let p=0,q=1;for(const [i,j]of [[0,2],[1,2]])if(Math.abs(a[i][j])>Math.abs(a[p][q])){p=i;q=j;}if(Math.abs(a[p][q])<1e-14)break;
   const phi=.5*Math.atan2(2*a[p][q],a[q][q]-a[p][p]),c=Math.cos(phi),s=Math.sin(phi),app=a[p][p],aqq=a[q][q],apq=a[p][q];
   for(let k=0;k<3;k++)if(k!==p&&k!==q){const x=a[k][p],y=a[k][q];a[k][p]=a[p][k]=c*x-s*y;a[k][q]=a[q][k]=s*x+c*y;}
   a[p][p]=c*c*app-2*c*s*apq+s*s*aqq;a[q][q]=s*s*app+2*c*s*apq+c*c*aqq;a[p][q]=a[q][p]=0;
   for(let k=0;k<3;k++){const x=v[k][p],y=v[k][q];v[k][p]=c*x-s*y;v[k][q]=s*x+c*y;}
  }return {principal:a.map((r,i)=>r[i]),rotation:R.fromAxes(v[0].map((_,i)=>v.map(r=>r[i])))};
 }
 try{for(const id of ['big-throw','small-throw']){
  const kind=id==='big-throw'?'spear':'bomb',asset=data.assets[kind],raw=data.settings.weaponScales[id][kind],scale=Array.isArray(raw)?raw:[raw,raw,raw],hulls=[];
  for(const points of asset.hulls||[asset.collision]){const s=new J.ConvexHullShapeSettings();s.mMaxConvexRadius=.001;for(const p of points){const x=new J.Vec3(...p);s.mPoints.push_back(x);J.destroy(x);}const r=s.Create();if(r.HasError())throw Error(kind+' convex');owned.push(s,r);hulls.push(r.Get());}
  let shape=hulls[0];if(hulls.length>1){const s=new J.StaticCompoundShapeSettings(),p=new J.Vec3(0,0,0),q=new J.Quat(0,0,0,1);for(const h of hulls)s.AddShapeShape(p,q,h,0);J.destroy(p);J.destroy(q);const r=s.Create();if(r.HasError())throw Error(kind+' compound');owned.push(s,r);shape=r.Get();}
  if(scale.some(x=>x!==1)){const v=new J.Vec3(...scale);shape=new J.ScaledShape(shape,v);J.destroy(v);owned.push(shape);}
  const com=arr(shape.GetCenterOfMass()),mass=shape.GetMassProperties();mass.ScaleToMass(asset.mass);const m=mass.mInertia,columns=[arr(m.GetAxisX()),arr(m.GetAxisY()),arr(m.GetAxisZ())];result[kind]={scale,mass:asset.mass,com,inertia:columns,...diagonalize(columns)};/* Shape mass properties are borrowed scratch in this binding. */
 }}finally{for(const o of owned.reverse())J.destroy(o);}return result;
}
