/* Whole-body momentum about COM. One shared mass model and one rigid correction. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass;
const {add,sub,mul,dot,cross,length,rotate,qm,qinv,qexp,qlog,qslerp}=R;
const identity=[0,0,0,1];
function measurement(a,rig,dt){
 if(!(dt>0&&Number.isFinite(dt)))throw Error('Momentum needs a positive finite timestep');
 const before=M.bodies(a,rig),inverse=before.map(body=>qinv(body.q)),total=rig.mass??rig.reduce((s,v)=>s+v.mass,0);
 let ca=[0,0,0];for(let i=0;i<rig.length;i++)ca=add(ca,mul(before[i].center,rig[i].mass/total));
 return b=>{
 const after=M.bodies(b,rig);let cb=[0,0,0];for(let i=0;i<rig.length;i++)cb=add(cb,mul(after[i].center,rig[i].mass/total));
 if(!(total>0))return {momentum:[0,0,0],bodies:after,center:cb};
 const center=mul(add(ca,cb),.5),translation=mul(sub(cb,ca),1/dt);let h=[0,0,0];
 for(let i=0;i<rig.length;i++){
  const x=before[i],y=after[i],body=rig[i],q=qslerp(x.q,y.q,.5),omega=mul(qlog(qm(y.q,inverse[i])),1/dt);
  const local=rotate(qinv(q),omega),spin=rotate(q,local.map((v,j)=>v*body.inertia[j]));
  const arm=sub(mul(add(x.center,y.center),.5),center),v=sub(mul(sub(y.center,x.center),1/dt),translation);
  h=add(h,add(spin,mul(cross(arm,v),body.mass)));
 }
 return {momentum:h,bodies:after,center:cb};
 };
}
const momentum=(a,b,rig,dt)=>measurement(a,rig,dt)(b).momentum;
// Reuse the candidate body frames already needed for momentum. This keeps
// the summation order and values of Mass.tensor without rebuilding geometry.
function tensor(measured,rig){
 const I=Array.from({length:3},()=>[0,0,0]);
 for(let k=0;k<rig.length;k++){
  const body=rig[k],sample=measured.bodies[k],r=sub(sample.center,measured.center),axes=R.toAxes(sample.q),rr=dot(r,r);
  for(let i=0;i<3;i++)for(let j=0;j<3;j++)I[i][j]+=axes.reduce((s,a,k)=>s+a[i]*a[j]*body.inertia[k],0)+body.mass*((i===j?rr:0)-r[i]*r[j]);
 }
 return I;
}
// Scaled Cholesky for the positive-definite whole-body inertia. A relative
// diagonal floor handles a degenerate test rig without an absolute mass scale.
function solve(I,v){
 if(I.some(row=>row.some(x=>!Number.isFinite(x)))||v.some(x=>!Number.isFinite(x)))throw Error('Non-finite momentum solve');
 const scale=Math.max(...I.map((row,i)=>Math.abs(row[i])));if(scale===0)return [0,0,0];
 const a=I.map((row,i)=>row.map((x,j)=>(x+I[j][i])/(2*scale))),b=mul(v,1/scale),floor=1e-12;
 const l00=Math.sqrt(Math.max(floor,a[0][0])),l10=a[1][0]/l00,l20=a[2][0]/l00;
 const l11=Math.sqrt(Math.max(floor,a[1][1]-l10*l10)),l21=(a[2][1]-l20*l10)/l11;
 const l22=Math.sqrt(Math.max(floor,a[2][2]-l20*l20-l21*l21));
 const y0=b[0]/l00,y1=(b[1]-l10*y0)/l11,y2=(b[2]-l20*y0-l21*y1)/l22;
 const x2=y2/l22,x1=(y1-l21*x2)/l11,x0=(y0-l10*x1-l20*x2)/l00;
 return [x0,x1,x2];
}
const velocity=(I,desired,joints)=>solve(I,sub(desired,joints));
function correct(previous,candidate,desired,rig,dt,{iterations=3,tolerance=1e-7,axis=null}={}){
 if(desired.some(x=>!Number.isFinite(x)))throw Error('Non-finite desired momentum');
 if(axis&&(!axis.every(Number.isFinite)||length(axis)<1e-12))throw Error('Momentum axis must be finite and nonzero');
 const direction=axis?R.unit(axis):null,selected=v=>direction?mul(direction,dot(v,direction)):v;
 const measure=measurement(previous,rig,dt);let pose=candidate,rotation=identity,measured=measure(pose),h=measured.momentum,fullResidual=sub(desired,h),residual=selected(fullResidual),used=0;
 const count=Math.max(0,Math.min(3,Math.floor(iterations)));
 for(;used<count&&length(residual)>tolerance;used++){
  // dH/dtheta = I/dt to first order. Remeasure the finite motion after each
  // correction rather than pretending that its differential estimate is exact.
  const I=tensor(measured,rig),increment=direction?mul(direction,dot(fullResidual,direction)/M.moment(I,direction)):solve(I,residual),delta=qexp(mul(increment,dt));
  rotation=R.unit(qm(delta,rotation));pose=M.rotateAboutCOM(candidate,rotation,rig);
  measured=measure(pose);h=measured.momentum;fullResidual=sub(desired,h);residual=selected(fullResidual);
 }
 // Axis control deliberately leaves transverse momentum unconstrained.
 return {pose,rotation,momentum:h,residual,fullResidual,error:length(residual),iterations:used,axis:direction};
}
const api={model:M.model,momentum,solve,velocity,correct};if(node)module.exports=api;else root.BodyflipMomentum=api;
})(globalThis);
