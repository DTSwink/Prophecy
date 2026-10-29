// Reduced, dissipative air model. All positions are metres; no target direction.
export function airShape(R,asset,scale,axis){
 const longScale=R.length(axis.map((v,i)=>v*scale[i])),areaScale=scale.reduce((a,b)=>a*b,1)/longScale;
 const points=asset.hulls?.flat()||asset.collision,projected=points.map(p=>R.dot(p.map((v,i)=>v*scale[i]),axis));
 // Effective normal-force area is tuned for visible short-range spear flight.
 // It is a reduced-model coefficient, not the literal mesh surface area.
 return {axis,mass:asset.mass,length:Math.max(...projected)-Math.min(...projected),sideArea:.96*longScale*Math.sqrt(areaScale),axialArea:.001*areaScale};
}

export function airForces(R,shape,settings,q,velocity,omega,inverseInertia,dt){
 const {add,sub,mul,dot,cross,length,unit,rotate}=R,axis=unit(rotate(q,shape.axis)),r=mul(axis,-settings.pressure*shape.length);
 const pointVelocity=add(velocity,cross(omega,r)),along=mul(axis,dot(pointVelocity,axis)),side=sub(pointVelocity,along);
 const densityFactor=.5*1.225*settings.strength;
 function drag(component,area,flowSpeed=length(component)){
  const speed=length(component);if(speed<1e-10)return [0,0,0];
  const normal=mul(component,1/speed),moment=cross(r,normal),inverseMass=1/shape.mass+dot(moment,inverseInertia(moment)),k=densityFactor*area*flowSpeed;
  // Implicit drag response bounds the impulse at high speed/small inertia.
  return mul(component,-k/(1+dt*k*inverseMass));
 }
 // Normal response depends on the full airflow: proportional to sin(alpha)
 // near alignment, rather than sin(alpha)^2 from transverse-only drag.
 const force=add(drag(side,shape.sideArea,length(pointVelocity)),drag(along,shape.axialArea)),swing=sub(omega,mul(axis,dot(omega,axis))),rate=length(swing);
 let torque=cross(r,force);
 if(rate>1e-10&&settings.damping>0){
  const normal=mul(swing,1/rate),k=densityFactor*shape.sideArea*shape.length**2/12*Math.max(length(velocity),rate*shape.length)*settings.damping;
  torque=sub(torque,mul(swing,k/(1+dt*k*dot(normal,inverseInertia(normal)))));
 }
 return {force,torque};
}
