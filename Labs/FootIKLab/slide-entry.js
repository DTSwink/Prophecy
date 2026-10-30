/* Host-only, fixed-pelvis wall-slide entry corridor. */
(function(root){
'use strict';
const R=typeof module==='object'&&module.exports?require('./recovery.js'):root.Recovery;
const S=typeof module==='object'&&module.exports?require('./support.js'):root.BodyflipSupport;
const {add,sub,mul,dot,length,rotate,qm,qinv,qslerp,unit}=R,IDENT=[0,0,0,1],RAD=Math.PI/180;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
function create({a,b,leg:l,parents,joints,poseAt,surfaces,inspect,bodyExponent=1,bodyProgress=u=>u,pelvis=-1,pelvisProgress=bodyProgress,quality=false,seed=0}){
 const started=Date.now(),hip=joints.joints[l.hip],knee=joints.joints[l.knee],N=quality?32:24,passes=quality?240:96;
 const positive=q=>q[3]<0?mul(q,-1):q;
 function swingVariables(j,q){q=joints.project(j.index,IDENT,q,false).q;const r=unit(qm(qm(qinv(j.c1),q),j.c2)),d=Math.hypot(r[0],r[3]),tw=positive(d>1e-12?[r[0]/d,0,0,r[3]/d]:IDENT),sw=positive(unit(qm(r,qinv(tw))));return [sw[1]/j.sinY,sw[2]/j.sinZ,2*Math.atan2(tw[0],tw[3])/j.twist];}
 function variables(hipQ,kneeQ,footQ){return [...swingVariables(hip,hipQ),joints.diagnose(l.knee,IDENT,kneeQ).bend/knee.max,...swingVariables(joints.joints[l.foot],footQ)];}
 function project(v){v=v.slice();v[2]=clamp(v[2],-1,1);v[3]=clamp(v[3],0,1);v[6]=clamp(v[6],-1,1);for(const i of[0,4]){const r=Math.hypot(v[i],v[i+1]);if(r>1){v[i]/=r;v[i+1]/=r;}}return v;}
 function jointRotation(j,v,at=0){const y=v[at]*j.sinY,z=v[at+1]*j.sinZ;return unit(qm(qm(j.c1,qm([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],R.qexp([v[at+2]*j.twist,0,0]))),qinv(j.c2)));}
 function hipRotation(v){return jointRotation(hip,v);}
 const aVars=variables(joints.project(l.hip,IDENT,a.q[l.hip],false).q,joints.project(l.knee,IDENT,a.q[l.knee],false).q,a.q[l.foot]),bVars=variables(b.q[l.hip],b.q[l.knee],b.q[l.foot]);
 const residual=[l.hip,l.knee].map(j=>qm(a.q[j],qinv(joints.project(j,IDENT,a.q[j],false).q))),residualAngle=residual.map(q=>length(R.qlog(q)));
 function sourceLocal(u){const bodyU=bodyProgress(u),p=a.p.map((v,i)=>add(v,mul(sub(b.p[i],v),bodyU))),q=a.q.map((v,i)=>qslerp(v,b.q[i],1-(1-bodyU)**bodyExponent));if(pelvis>=0){const t=pelvisProgress(u);p[pelvis]=add(a.p[pelvis],mul(sub(b.p[pelvis],a.p[pelvis]),t));q[pelvis]=qslerp(a.q[pelvis],b.q[pelvis],1-(1-t)**bodyExponent);}for(const j of[l.hip,l.knee,l.foot,l.toe])q[j]=joints.blendLocal(j,a.q[j],b.q[j],u);for(const j of[l.knee,l.foot,l.toe])p[j]=R.offsetBlend(a.p[j],b.p[j],u);return {p,q};}
 function footAt(c,v){return unit(qm(c.footResidual,jointRotation(joints.joints[l.foot],v,4)));}
 function cache(u,override=null){const local=override||sourceLocal(u),pose=override?R.fk(local,parents):poseAt?poseAt(u,local):R.fk(local,parents),footInverse=qinv(pose.q[l.foot]);return {u,live:!!override,local,footResidual:u>=1?IDENT:qm(local.q[l.foot],qinv(joints.project(l.foot,IDENT,local.q[l.foot],false).q)),hipPoint:pose.points[l.hip],parentQ:pose.q[parents[l.hip]],corners:S.footPoints(pose,l.foot,l.toe,l.side).map(v=>rotate(footInverse,v)),wanted:variables(local.q[l.hip],local.q[l.knee],local.q[l.foot]),residual:residual.map(q=>qslerp(q,IDENT,u))};}
 // An incoming NN residual is allowed to retire, never to grow as the legal
 // part turns underneath it. Skip projection entirely for valid source joints.
 function retireResidual(q,index,c){const bound=residualAngle[index]*(1-c.u);if(!c.live||residualAngle[index]<1e-7||c.u<=0||c.u>=1)return q;const j=index?l.knee:l.hip;for(let k=0;k<2;k++){const legal=joints.project(j,IDENT,q,false).q,error=2*Math.acos(clamp(Math.abs(dot(q,legal)),-1,1));if(error<=bound+1e-8)break;q=qslerp(legal,q,bound/error);}return q;}
 function rotations(v,c){const q=[retireResidual(unit(qm(c.residual[0],hipRotation(v))),0,c),retireResidual(unit(qm(c.residual[1],joints.hingeRelative(knee,v[3]*knee.max))),1,c)];return c.u>=1?q.map((v,i)=>joints.project(i?l.knee:l.hip,IDENT,v,false).q):q;}
 function evaluateGeometry(c,v){const [h,k]=rotations(v,c),hipQ=qm(c.parentQ,h),kneePoint=add(c.hipPoint,rotate(hipQ,c.local.p[l.knee])),kneeQ=qm(hipQ,k),footPoint=add(kneePoint,rotate(kneeQ,c.local.p[l.foot])),footQ=qm(kneeQ,footAt(c,v));let penetration=0,kneePenetration=0,min=Infinity,planeName=null;const constraints=[];const corners=c.corners.map(v=>add(footPoint,rotate(footQ,v)));
  for(const plane of typeof surfaces==='function'?surfaces(c.u,c.live):surfaces){const[x0,x1,z0,z1]=plane.bounds,below=at=>plane.finiteSlab&&at[1]<-plane.box.dims[1]-.04;
   let shoeError=0,kneeError=0;for(const p of corners){const at=plane.local(p);if(below(at))continue;if(at[0]>=x0&&at[0]<=x1&&at[2]>=z0&&at[2]<=z1){if(at[1]<min){min=at[1];planeName=plane.id;}penetration=Math.max(penetration,.012-at[1]);shoeError=Math.max(shoeError,.012-at[1]);}}
   const at=plane.local(kneePoint);if(!below(at)&&at[0]>=x0&&at[0]<=x1&&at[2]>=z0&&at[2]<=z1){kneePenetration=Math.max(kneePenetration,.085-at[1]);kneeError=Math.max(kneeError,.085-at[1]);}
   constraints.push(shoeError,kneeError);
  }
  return {penetration:Math.max(0,penetration),kneePenetration:Math.max(0,kneePenetration),min,planeName,constraints};
 }
 // Simultaneous contact projection: coordinate descent alone can get stuck
 // when a hip/knee correction must move several joint coordinates together.
 function correct(c,input,margin=.012,iterations=18){let v=input.slice();
  const errors=g=>g.constraints.map((x,i)=>Math.max(0,x+(i%2?0:margin-.012)));
  const cost=g=>errors(g).reduce((sum,x)=>sum+x*x,0);
  for(let step=0;step<iterations;step++){
   const base=evaluateGeometry(c,v),e=errors(base);if(Math.max(...e)<1e-5)break;
   const rows=e.map(()=>[]),eps=.0002;
   for(let axis=0;axis<7;axis++){const a=v.slice(),b=v.slice();a[axis]+=eps;b[axis]-=eps;const ga=evaluateGeometry(c,project(a)).constraints,gb=evaluateGeometry(c,project(b)).constraints;for(let j=0;j<rows.length;j++)rows[j][axis]=(ga[j]-gb[j])/(2*eps);}
   // Solve every active plane together. Collapsing floor and wall to their
   // maximum penetration lets one correction push the shoe through the other.
   const scalar=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0),h=rows.map(a=>rows.map(b=>scalar(a,b))),lambda=e.map(()=>0);
   for(let sweep=0;sweep<16;sweep++)for(let j=0;j<e.length;j++){if(!e[j])continue;const response=h[j].reduce((sum,x,k)=>sum+x*lambda[k],0);lambda[j]=Math.max(0,lambda[j]+(e[j]-response)/(h[j][j]+1e-6));}
   let delta=Array.from({length:7},(_,i)=>-rows.reduce((sum,row,j)=>sum+lambda[j]*row[i],0)),n=Math.hypot(...delta);if(n>.25)delta=delta.map(x=>x*.25/n);
   let best=v,bestCost=cost(base);for(const scale of[1,.5,.25,.125]){const test=project(v.map((x,i)=>x+delta[i]*scale)),score=cost(evaluateGeometry(c,test));if(score<bestCost){best=test;bestCost=score;}}
   if(best===v)break;v=best;
  }return v;
 }

 const tracked=[l.hip,l.knee,l.foot];let previousSolved=null;
 function remember(local){previousSolved=tracked.map(j=>local.q[j].slice());return local;}
 // Once entry is complete, carry the actual legal pose rather than an offset
 // in normalized joint coordinates. The latter grows stale when the target
 // turns, and can keep folding a leg long after the obstacle has cleared.
 function settledSample(local){
  const candidate={p:local.p,q:local.q.slice()};
  for(let i=0;i<tracked.length;i++){
   const j=tracked[i],from=previousSolved?.[i]||local.q[j],to=local.q[j],angle=length(R.qlog(qm(to,qinv(from))));
   candidate.q[j]=joints.blendLocal(j,from,to,Math.min(1,4/120/Math.max(angle,1e-8)));
  }
  const c=cache(1,candidate),base=variables(candidate.q[l.hip],candidate.q[l.knee],candidate.q[l.foot]),g=evaluateGeometry(c,base);
  const v=(g.min<0||g.kneePenetration>.002)?correct(c,base,0,24):base,[h,k]=rotations(v,c);
  local.q[l.hip]=h;local.q[l.knee]=k;local.q[l.foot]=footAt(c,v);return remember(local);
 }

 const nodes=Array.from({length:N+1},(_,k)=>cache(k/N));
 // The normal joint blend is the preferred path whenever it already clears.
 let bad=false;for(let i=1;i<N;i++){const g=evaluateGeometry(nodes[i],nodes[i].wanted);if(g.penetration>.0121||g.kneePenetration>.002)bad=true;}
 // A clear entry can still turn its knee toward the wall later. Resolve that
 // as it approaches, rather than waiting for a shoe collision to trigger it.
 if(!bad){let carry=Array(7).fill(0);return {active:false,milliseconds:Date.now()-started,sample:(u,local)=>{if(u<=0)return remember(local);if(u>=1)return settledSample(local);const c=cache(u,local),base=variables(local.q[l.hip],local.q[l.knee],local.q[l.foot]),margin=.008*4*u*(1-u),seed=project(base.map((x,i)=>x+carry[i]*.92)),g=evaluateGeometry(c,seed),v=(g.min<margin||g.kneePenetration>.002)?correct(c,seed,margin,24):seed;carry=v.map((x,i)=>x-base[i]);if(!carry.some(x=>Math.abs(x)>1e-10))return remember(local);const[h,k]=rotations(v,c);local.q[l.hip]=h;local.q[l.knee]=k;local.q[l.foot]=footAt(c,v);return remember(local);},diagnostics:{maxPenetration:0}};}
 const keys=seed?[[0,aVars],[.2,[...aVars.slice(0,3),.4,...aVars.slice(4)]],[.5,[...aVars.slice(0,3).map((x,j)=>(x+bVars[j])*.5),.4,0,0,0]],[.8,[...bVars.slice(0,3),.4,...bVars.slice(4)]],[1,bVars]]:[[0,aVars],[.12,[...aVars.slice(0,3),1,0,0,0]],[.48,[0,0,0,1,0,0,0]],[.8,[...bVars.slice(0,3),1,0,0,0]],[1,bVars]];
 for(const c of nodes){let i=1;while(i<keys.length-1&&c.u>keys[i][0])i++;const[t0,v0]=keys[i-1],[t1,v1]=keys[i],t=(c.u-t0)/(t1-t0);c.v=v0.map((x,j)=>x+(v1[j]-x)*t);}
 let obstacleWeight=1000;
 function evaluate(i,v){const c=nodes[i],g=evaluateGeometry(c,v),regularity=v.reduce((sum,x,j)=>sum+(x-c.wanted[j])**2*.002+(x-nodes[i-1].v[j])**2*4+(x-nodes[i+1].v[j])**2*4,0);return {v,cost:obstacleWeight*(g.penetration*g.penetration+g.kneePenetration*g.kneePenetration)+regularity};}
 for(let iteration=0;iteration<passes;iteration++){obstacleWeight=1000*Math.pow(100,iteration/(passes-1));for(let p=1;p<N;p++){const i=iteration%2?p:N-p;let best=evaluate(i,nodes[i].v);for(let refine=0;refine<4;refine++){const step=.12*Math.pow(quality?.993:.982,iteration)*Math.pow(.5,refine);for(let axis=0;axis<7;axis++)for(const sign of[-1,1]){const v=best.v.slice();v[axis]+=step*sign;const result=evaluate(i,project(v));if(result.cost<best.cost)best=result;}}nodes[i].v=best.v;}}
 for(let i=1;i<N;i++)nodes[i].v=correct(nodes[i],nodes[i].v);
 inspect?.({nodes,evaluateGeometry,correct,project});
 const offsets=nodes.map(c=>c.v.map((x,i)=>x-c.wanted[i]));offsets[0]=[0,0,0,0,0,0,0];offsets[N]=[0,0,0,0,0,0,0];
 const slopes=offsets.map(()=>Array(7).fill(0));for(let i=1;i<N;i++)for(let j=0;j<7;j++){const a=(offsets[i][j]-offsets[i-1][j])*N,b=(offsets[i+1][j]-offsets[i][j])*N;if(a*b>0)slopes[i][j]=2*a*b/(a+b);}
 function values(u,local){if(u<=0||u>=1)return variables(local.q[l.hip],local.q[l.knee],local.q[l.foot]);const t=u*N,i=Math.min(N-1,Math.floor(t)),f=t-i,f2=f*f,f3=f2*f,base=variables(local.q[l.hip],local.q[l.knee],local.q[l.foot]);return project(base.map((x,j)=>x+(2*f3-3*f2+1)*offsets[i][j]+(f3-2*f2+f)*slopes[i][j]/N+(-2*f3+3*f2)*offsets[i+1][j]+(f3-f2)*slopes[i+1][j]/N));}
 let correction=Array(7).fill(0);
 function sample(u,local,refine=true){if(u<=0)return refine?remember(local):local;if(u>=1&&refine)return settledSample(local);let v=values(u,local);const desired=v.slice();let c;
  if(refine){c=cache(u,local);const margin=.008*4*u*(1-u),seed=project(v.map((x,i)=>x+correction[i]*.92)),g=evaluateGeometry(c,seed);v=(g.min<margin||g.kneePenetration>.002)?correct(c,seed,margin,24):seed;correction=v.map((x,i)=>x-desired[i]);}
  else c={u,residual:residual.map(q=>qslerp(q,IDENT,u)),footResidual:u>=1?IDENT:qm(local.q[l.foot],qinv(joints.project(l.foot,IDENT,local.q[l.foot],false).q))};
  const[h,k]=rotations(v,c);local.q[l.hip]=h;local.q[l.knee]=k;local.q[l.foot]=footAt(c,v);return refine?remember(local):local;}
 let maxPenetration=0,minKnee=Infinity,maxHipStep=0,last=null,totalAngle=0,worst=null;const timing=[{u:0,distance:0}];for(let k=0;k<=240;k++){const u=k/240,c=cache(u),v=values(u,c.local),g=evaluateGeometry(c,v),local=sample(u,c.local,false),hipQ=qm(c.parentQ,local.q[l.hip]),kneeQ=qm(hipQ,local.q[l.knee]),footQ=qm(kneeQ,local.q[l.foot]),current=[hipQ,kneeQ,footQ];if(g.penetration-.012>maxPenetration)worst={u,plane:g.planeName,v};maxPenetration=Math.max(maxPenetration,g.penetration-.012);minKnee=Math.min(minKnee,.085-g.kneePenetration);if(last){const delta=current.map((q,j)=>length(R.qlog(qm(q,qinv(last[j])))));maxHipStep=Math.max(maxHipStep,delta[0]/RAD);totalAngle+=Math.max(...delta);timing.push({u,distance:totalAngle});}last=current;}
 // A fully folded waypoint can trap the corridor on the wrong side of the
 // wall. Try one moderate-bend route before spending more iterations there.
 // Ordinary clear paths never pay for this second seed.
 if(!seed&&(maxHipStep>2||(worst&&worst.u<.95&&maxPenetration>.008))){
  const alternative=create({a,b,leg:l,parents,joints,poseAt,surfaces,inspect,bodyExponent,bodyProgress,pelvis,pelvisProgress,quality:false,seed:1});
  const score=d=>Math.max(0,(d.worst&&d.worst.u<.95?d.maxPenetration:0)-.005)*1000+Math.max(0,d.maxHipStep-2);
  if(score(alternative.diagnostics)<score({maxPenetration,maxHipStep,worst}))return {...alternative,milliseconds:Date.now()-started};
 }
 if(!quality&&(maxHipStep>2||(worst&&worst.u<.95&&maxPenetration>.008))){const refined=create({a,b,leg:l,parents,joints,poseAt,surfaces,inspect,bodyExponent,bodyProgress,pelvis,pelvisProgress,quality:true,seed});return {...refined,milliseconds:Date.now()-started};}
 return {active:true,milliseconds:Date.now()-started,sample,diagnostics:{maxPenetration,minKnee,maxHipStep,totalAngle:totalAngle/RAD,worst},timing,nodes:offsets};
}
const api={create};if(typeof module==='object'&&module.exports)module.exports=api;else root.SlideEntry=api;
})(typeof globalThis!=='undefined'?globalThis:this);


