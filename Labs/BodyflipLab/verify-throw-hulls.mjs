// Approved hull settings and native coordinate/scale order, without a world.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import init from './vendor/jolt.mjs';
const J=await init(),data=JSON.parse(fs.readFileSync(new URL('../../Content/BodyflipLab/Projectiles.json',import.meta.url))),rows=[];
const defaults=new J.ConvexHullShapeSettings();
assert(Math.abs(defaults.mHullTolerance-.001)<1e-10);assert(Math.abs(defaults.mMaxErrorConvexRadius-.05)<1e-8);J.destroy(defaults);
const arr=v=>[v.GetX(),v.GetY(),v.GetZ()],reflect=p=>[p[0],p[2],p[1]],distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
for(const kind of ['spear','bomb']){
 const asset=data.assets[kind],scale=data.physical[kind].scale,nativeScale=reflect(scale),owned=[];let strictFailures=0;
 function hull(points,tolerance){const s=new J.ConvexHullShapeSettings();s.mHullTolerance=tolerance;s.mMaxConvexRadius=.001;s.mMaxErrorConvexRadius=.05;for(const p of points){const v=new J.Vec3(...p);s.mPoints.push_back(v);J.destroy(v);}const r=s.Create();owned.push(s,r);return r;}
 function compound(hulls,scale){let shape=hulls[0];if(hulls.length>1){const s=new J.StaticCompoundShapeSettings(),p=new J.Vec3(0,0,0),q=new J.Quat(0,0,0,1);for(const h of hulls)s.AddShapeShape(p,q,h,0);J.destroy(p);J.destroy(q);const r=s.Create();assert(!r.HasError());owned.push(s,r);shape=r.Get();}const v=new J.Vec3(...scale),result=new J.ScaledShape(shape,v);J.destroy(v);owned.push(result);return result;}
 try{
  const original=[],native=[];for(const points of asset.hulls||[asset.collision]){
   const a=hull(points,.001);assert(!a.HasError(),kind+' approved hull');original.push(a.Get());
   const scaled=points.map(p=>reflect(p.map((x,i)=>x*scale[i]*100))),b=hull(scaled.map(p=>p.map((x,i)=>x/nativeScale[i]*.01)),.001);assert(!b.HasError(),kind+' native-order hull');native.push(b.Get());
   if(hull(scaled.map(p=>p.map(x=>x*.01)),0).HasError())strictFailures++;
  }
  const a=compound(original,scale),b=compound(native,nativeScale),ac=arr(a.GetCenterOfMass()),bc=arr(b.GetCenterOfMass()),ab=a.GetLocalBounds(),amin=arr(ab.mMin),amax=arr(ab.mMax),bb=b.GetLocalBounds(),bmin=arr(bb.mMin),bmax=arr(bb.mMax);
  const comError=distance(reflect(ac),bc),minError=distance(reflect(amin.map((x,i)=>x+ac[i])),bmin.map((x,i)=>x+bc[i])),maxError=distance(reflect(amax.map((x,i)=>x+ac[i])),bmax.map((x,i)=>x+bc[i]));
  assert(comError<1e-6&&minError<1e-6&&maxError<1e-6,kind+' bounds/COM differ from approved scaled hulls');rows.push({kind,hulls:original.length,strictFailures,comError,minError,maxError});
 }finally{for(const o of owned.reverse())J.destroy(o);}
}
assert(rows.some(r=>r.strictFailures>0),'fixture must expose preliminary zero-tolerance failure');
const report={passed:true,hullTolerance:.001,maxErrorConvexRadius:.05,maxConvexRadius:.001,rows};fs.writeFileSync(new URL('../../Saved/Diagnostics/BodyflipPort20261030/throw-hulls.json',import.meta.url),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
