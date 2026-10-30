/* Kinematic slide joints in the same reference frames/limits as Bodyflip Jolt.
 * Reference: data/rig.json sharedIdle (M_Neutral_Stand_Idle_Loop.npz, frame 0).
 * Limits/frame construction: ../BodyflipLab/physics.mjs createPhysics.
 * Cone projection follows Jolt SwingTwistConstraintPart::ClampSwingTwist:
 * closest point on its quaternion-space ellipse, rather than Euler clamps.
 * No state, FK traversal, physics worker, or network request is used here.
 */
(function(root){
'use strict';
const R=typeof module==='object'&&module.exports?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,unit,qm,qinv,rotate,fromAxes,toAxes,qexp}=R;
const RAD=Math.PI/180,IDENT=[0,0,0,1],clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const DEFAULT_REFERENCE={"names":["root","pelvis","spine_01","spine_02","spine_03","spine_04","spine_05","clavicle_l","upperarm_l","lowerarm_l","hand_l","clavicle_r","upperarm_r","lowerarm_r","hand_r","neck_01","neck_02","head","thigh_l","calf_l","foot_l","ball_l","thigh_r","calf_r","foot_r","ball_r"],"parents":[-1,0,1,2,3,4,5,6,7,8,9,6,11,12,13,6,15,16,1,18,19,20,1,22,23,24],"points":[[0,0,0],[0.021300818920135498,0.9059066772460938,-0.02506947994232178],[0.0231626558303833,0.9733444213867187,-0.031769146919250486],[0.022193589210510255,1.0459832000732423,-0.027665088176727297],[0.021247627735137938,1.1058324432373048,-0.02437720775604248],[0.020421946048736574,1.1868512725830078,-0.02124836206436157],[0.018338340520858764,1.2868775939941406,-0.014359904527664185],[0.038920350074768066,1.3304400634765625,-0.0034556326270103457],[0.18721717834472656,1.3129158020019531,0.0385008430480957],[0.2708499145507813,1.0598643493652344,0.038431944847106936],[0.28835113525390627,0.8552622222900391,0.12663691520690917],[-0.003671608567237854,1.330440216064453,-0.02198115348815918],[-0.13382299423217775,1.3107106018066406,-0.10402249336242676],[-0.18764448165893555,1.0678377532958985,-0.1996548843383789],[-0.2479022789001465,0.8547993469238282,-0.16912469863891602],[0.014362891912460327,1.3995863342285157,-0.005219902992248535],[0.010584876537322999,1.442821044921875,0.008861570954322814],[0.006981267929077149,1.4953762817382812,0.020335931777954102],[0.09594319343566894,0.8802133941650391,-0.004215589165687561],[0.14510868072509767,0.5158390426635743,0.12557214736938477],[0.19993988037109375,0.09375221252441407,0.12542905807495117],[0.18016929626464845,0.03215306997299194,0.2624412155151367],[-0.05339873313903809,0.8802133941650391,-0.0457176160812378],[-0.14012736320495606,0.5018156051635743,-0.08338558197021484],[-0.1448523998260498,0.09372957229614258,-0.20424600601196288],[-0.23128534317016602,0.032130177021026614,-0.09611405372619629]],"q":[[-0.7071067811865475,0,0,0.7071067811865476],[0.5653283997567417,0.5606069093674269,-0.42964763759205726,-0.4260593868342157],[0.5663359126423076,0.5596650131390742,-0.42854837699037895,-0.42706556370018445],[0.5568381335374137,0.5824274231244339,-0.40793860461799863,-0.42929673268442337],[0.5661289909307797,0.5842813601692627,-0.4028819193538017,-0.41928441044743187],[0.5630206185631392,0.6014175410421507,-0.38489288547912365,-0.4161276139685361],[0.5688739716039439,0.6130346067713514,-0.3729216875223959,-0.40187111156152816],[-0.6307358841214411,-0.06890288032214287,-0.13121573314368057,0.7617132458743401],[-0.44305256058435216,0.3203285633944606,-0.490395925131252,0.6786795095241593],[-0.47339148709553575,0.19646944773122413,-0.649804307008502,0.5612972640650099],[0.7238761393208958,-0.5784436475172071,0.36003919357805614,-0.1085267739155976],[0.7185747419957723,-0.1329197724796124,0.2505785148366631,0.6349748673388024],[0.5742387905573171,0.27990216254488065,0.5662874453106526,0.5207908602361445],[0.4998389583933795,0.4420369188785896,0.4120598758377709,0.6204603426046706],[0.022664226694083616,0.08234686873690641,0.6274622388349308,0.7739486190141064],[-0.43920189620989364,-0.6271924804199828,0.3847478349994215,0.5154613373799446],[0.47027256251985733,0.6042453555268456,-0.41025312126305685,-0.49540250681558184],[-0.4534295342620779,-0.5431887408175473,0.4744633249173586,0.5236718463086283],[-0.5680008377776348,-0.4787521956412209,0.5777946349848839,0.33811942155886254],[0.4881980910622512,0.5624157023897715,-0.5031931646216816,-0.4383467128502405],[0.5229672713545098,0.5229701967368502,-0.4759232728114405,-0.4759248310536927],[-0.0008631296638382289,-0.7395320856048216,0.0007853123853868116,0.6731202958258081],[-0.5761231580586056,0.6889918666188346,0.3693381549063012,-0.2386663818221622],[0.6733042036001009,-0.5970360771652733,-0.38999647805773663,0.19522325445524444],[0.6445992120537155,-0.6445957894776275,-0.2906802486048114,0.29067699784896633],[0.911632648683731,-0.0010637470650262763,-0.4110043217398912,0.0004793821009161148]],"source":"C:\\Users\\singerie\\Documents\\Cursor\\stepper\\training\\slashes2\\walk_run_sword_prep\\authored_pruned_npz\\walk_omni\\M_Neutral_Stand_Idle_Loop.npz","sha256":"90137cbd69a18fd521f511e92410b0db418e7054573adf5ed12e56235702e156"};
const angleBetween=(a,b)=>2*Math.atan2(length(qm(qinv(a),b).slice(0,3)),Math.abs(qm(qinv(a),b)[3]));
const positive=q=>q[3]<0?mul(q,-1):q;
const orthogonal=(v,n)=>sub(v,mul(n,dot(v,n)));
function perpendicular(v){const a=Math.abs(v[0])<.8?[1,0,0]:[0,1,0];return unit(cross(v,a));}
function decompose(q){
 q=unit(q);const n=Math.hypot(q[0],q[3]);
 const twist=n>1e-12?[q[0]/n,0,0,q[3]/n]:IDENT;
 return {swing:positive(unit(qm(q,qinv(twist)))),twist:positive(twist)};
}
// Lagrange multiplier solve for the Euclidean closest point on an ellipse.
// Called only outside it. Unlike radial scaling this matches Jolt's cone shape
// and nearest-point correction for mixed-axis swings.
function ellipseClosest(y,z,a,b){
 if((y/a)**2+(z/b)**2<=1)return [y,z];
 const a2=a*a,b2=b*b;
 let lo=0,hi=Math.hypot(a*y,b*z);
 for(let k=0;k<38;k++){
  const t=(lo+hi)*.5,ey=a*y/(t+a2),ez=b*z/(t+b2);
  if(ey*ey+ez*ez>1)lo=t;else hi=t;
 }
 return [a2*y/(hi+a2),b2*z/(hi+b2)];
}
const polynomialAdd=(a,b,s=1)=>Array.from({length:Math.max(a.length,b.length)},(_,i)=>(a[i]||0)+s*(b[i]||0));
function polynomialProduct(a,b){const out=Array(a.length+b.length-1).fill(0);for(let i=0;i<a.length;i++)for(let j=0;j<b.length;j++)out[i+j]+=a[i]*b[j];return out;}
function realRoots(input){
 // All polynomials here have degree at most four. Derivative roots partition
 // them into monotone intervals, so bisection finds even narrow feasible arcs
 // without angular sampling or choosing between coarse elbow-pole candidates.
 const scale=Math.max(...input.map(Math.abs));if(scale<1e-16)return [];
 const p=input.map(x=>x/scale);while(p.length>1&&Math.abs(p.at(-1))<1e-13)p.pop();
 const n=p.length-1;if(!n)return [];if(n===1)return [-p[0]/p[1]];
 const value=x=>{let y=p[n];for(let i=n-1;i>=0;i--)y=y*x+p[i];return y;};
 const bound=1+Math.max(...p.slice(0,-1).map(x=>Math.abs(x/p[n])));
 const critical=realRoots(p.slice(1).map((x,i)=>x*(i+1))).filter(x=>x>-bound&&x<bound).sort((a,b)=>a-b);
 const cuts=[-bound,...critical,bound],roots=[];
 for(const x of critical)if(Math.abs(value(x))<1e-10)roots.push(x);
 for(let i=1;i<cuts.length;i++){
  let lo=cuts[i-1],hi=cuts[i],flo=value(lo),fhi=value(hi);
  if(flo===0)roots.push(lo);if(fhi===0)roots.push(hi);
  if((flo<0)===(fhi<0))continue;
  for(let k=0;k<90;k++){const mid=(lo+hi)*.5;if(mid===lo||mid===hi)break;const fmid=value(mid);if((flo<0)===(fmid<0)){lo=mid;flo=fmid;}else hi=mid;}
  roots.push((lo+hi)*.5);
 }
 return roots.sort((a,b)=>a-b).filter((x,i,a)=>!i||Math.abs(x-a[i-1])>1e-9*(1+Math.abs(x)));
}
function limits(name){
 if(name.startsWith('foot'))return [40,28,25];
 if(name.startsWith('ball'))return [35,8,8];
 if(name.startsWith('upperarm'))return [130,110,100];
 if(name.startsWith('thigh'))return [105,75,65];
 if(name.startsWith('clavicle'))return [35,35,30];
 if(name.startsWith('spine'))return [22,22,22];
 return [45,40,55];
}
function build(input,names,parents){
 names=names||DEFAULT_REFERENCE.names;parents=parents||DEFAULT_REFERENCE.parents;
 const source=input||DEFAULT_REFERENCE;
 const sourceNames=source.names||names;
 const order=names.map(n=>sourceNames.indexOf(n));
 if(order.some(i=>i<0))throw Error('Slide joint reference is missing a rig bone');
 const sourceQ=source.q||source.axes.map(fromAxes);
 const reference={points:order.map(i=>source.points[i].slice()),q:order.map(i=>unit(sourceQ[i].slice())),names:names.slice(),parents:parents.slice(),source:source.source,sha256:source.sha256};
 reference.axes=reference.q.map(toAxes);
 const joints=names.map((name,i)=>{
  const parent=parents[i];if(i<2||parent<0)return null;
  const refRelative=unit(qm(qinv(reference.q[parent]),reference.q[i]));
  if(/^(calf|lowerarm)_/.test(name)){
   const child=parents.findIndex(p=>p===i);if(child<0)return null;
   const incoming=unit(sub(reference.points[i],reference.points[parent])),outgoing=unit(sub(reference.points[child],reference.points[i]));
   let axis=unit(cross(incoming,outgoing));if(length(axis)<.1)axis=rotate(reference.q[i],[0,0,1]);
   const idleBend=Math.acos(clamp(dot(incoming,outgoing),-1,1));
   return {index:i,parent,child,name,type:'hinge',refRelative,axisParent:rotate(qinv(reference.q[parent]),axis),axisChild:rotate(qinv(reference.q[i]),axis),axisReference:axis,incoming,idleBend,min:0,max:(name.startsWith('calf')?150:155)*RAD};
  }
  // Jolt builds its constraint basis from [twist, plane x twist, plane].
  // Bodyflip passes child X and child Y: the basis is [child X,-child Z,child Y].
  const twist=rotate(reference.q[i],[1,0,0]),plane=rotate(reference.q[i],[0,1,0]);
  const constraintWorld=fromAxes([twist,cross(plane,twist),plane]),degrees=limits(name);
  return {index:i,parent,name,type:'swingTwist',degrees,refRelative,c1:unit(qm(qinv(reference.q[parent]),constraintWorld)),c2:unit(qm(qinv(reference.q[i]),constraintWorld)),swingY:degrees[1]*RAD,swingZ:degrees[0]*RAD,twist:degrees[2]*RAD,sinY:Math.sin(degrees[1]*RAD/2),sinZ:Math.sin(degrees[0]*RAD/2)};
 });
 function hingeRelative(j,bend){return unit(qm(qexp(mul(j.axisParent,bend-j.idleBend)),j.refRelative));}
 function diagnose(index,parentQ,childQ){
  const j=joints[index];if(!j)return {withinLimits:true,type:'none'};
  if(j.type==='hinge'){
   const relative=unit(qm(qinv(parentQ),childQ)),delta=positive(unit(qm(relative,qinv(j.refRelative))));
   const along=dot(delta.slice(0,3),j.axisParent),theta=2*Math.atan2(along,delta[3]),bend=j.idleBend+theta;
   const hingeError=angleBetween(relative,hingeRelative(j,bend));
   const axisError=Math.acos(clamp(dot(rotate(parentQ,j.axisParent),rotate(childQ,j.axisChild)),-1,1));
   return {type:j.type,bend,bendDeg:bend/RAD,hingeError,axisError,withinLimits:bend>=j.min-1e-8&&bend<=j.max+1e-8&&hingeError<1e-7};
  }
  const relative=unit(qm(qinv(qm(parentQ,j.c1)),qm(childQ,j.c2))),{swing,twist}=decompose(relative);
  const ellipse=(swing[1]/j.sinY)**2+(swing[2]/j.sinZ)**2,twistAngle=2*Math.atan2(twist[0],twist[3]);
  return {type:j.type,ellipse,twist:twistAngle,twistDeg:twistAngle/RAD,swingY:2*Math.asin(clamp(swing[1],-1,1)),swingZ:2*Math.asin(clamp(swing[2],-1,1)),withinLimits:ellipse<=1+1e-8&&Math.abs(twistAngle)<=j.twist+1e-8};
 }
 function project(index,parentQ,childQ,diagnostics=true){
  const j=joints[index];if(!j)return {q:childQ.slice(),changed:false,correctionRad:0,before:{withinLimits:true},after:{withinLimits:true}};
  const before=diagnostics||j.type==='hinge'?diagnose(index,parentQ,childQ):null;let q;
  if(j.type==='hinge')q=unit(qm(parentQ,hingeRelative(j,clamp(before.bend,j.min,j.max))));
  else{
   const relative=unit(qm(qinv(qm(parentQ,j.c1)),qm(childQ,j.c2))),parts=decompose(relative);
   const yz=ellipseClosest(parts.swing[1],parts.swing[2],j.sinY,j.sinZ);
   const swing=[0,yz[0],yz[1],Math.sqrt(Math.max(0,1-yz[0]*yz[0]-yz[1]*yz[1]))];
   const twist=qexp([clamp(2*Math.atan2(parts.twist[0],parts.twist[3]),-j.twist,j.twist),0,0]);
   q=unit(qm(qm(qm(parentQ,j.c1),qm(swing,twist)),qinv(j.c2)));
  }
  if(dot(q,childQ)<0)q=mul(q,-1);
  if(!diagnostics)return {q};
  const correctionRad=angleBetween(q,childQ);
  return {q,changed:correctionRad>1e-8,correctionRad,before,after:diagnose(index,parentQ,q)};
 }
 // Interpolate inside the constraint domain, not along a quaternion geodesic
 // that may cross the excluded side of a wide hip cone. The swing ellipse
 // and bounded twist interval are convex in these coordinates.
 function blendLocal(index,from,to,t){
  if(t<=0)return from.slice();if(t>=1)return to.slice();
  const j=joints[index];if(!j)return R.qslerp(from,to,t);
  const a=project(index,IDENT,from,false).q,b=project(index,IDENT,to,false).q;
  let legal;
  if(j.type==='hinge'){
   const x=diagnose(index,IDENT,a).bend,y=diagnose(index,IDENT,b).bend;
   legal=hingeRelative(j,x+(y-x)*t);
  }else{
   const parts=q=>decompose(qm(qm(qinv(j.c1),q),j.c2)),x=parts(a),y=parts(b);
   const sy=x.swing[1]+(y.swing[1]-x.swing[1])*t,sz=x.swing[2]+(y.swing[2]-x.swing[2])*t;
   const angle=p=>2*Math.atan2(p.twist[0],p.twist[3]),twist=angle(x)+(angle(y)-angle(x))*t;
   legal=unit(qm(qm(j.c1,qm([0,sy,sz,Math.sqrt(Math.max(0,1-sy*sy-sz*sz))],qexp([twist,0,0]))),qinv(j.c2)));
  }
  // Preserve an already invalid incoming NN pose at t=0, then retire only
  // that residual. A valid entry stays legal for the complete path.
  return unit(qm(R.qslerp(qm(from,qinv(a)),IDENT,t),legal));
 }
 const arms={};
 for(const side of ['l','r']){
  const lower=names.indexOf('lowerarm_'+side),j=joints[lower];if(!j)continue;
  const upper=j.parent,hand=j.child,normal=j.axisReference;
  const basis=fromAxes([j.incoming,normal,cross(j.incoming,normal)]);
  arms[side]={upper,lower,hand,j,basisToBody:unit(qm(qinv(basis),reference.q[upper])),forearmDirection:unit(rotate(qinv(reference.q[lower]),sub(reference.points[hand],reference.points[lower])))};
 }
 // Generic hinge-chain swivel: rotate its proximal joint about the fixed
 // proximal-to-endpoint axis until its swing/twist cone is feasible. The
 // caller applies the returned WORLD-axis angle to both segment rotations
 // and the middle-joint position, leaving the endpoint untouched. Poles are
 // world-space bend directions; currentPole breaks equal-distance ties.
 // Works for shoulders/elbows and hips/knees with the same Jolt frames.
 function feasibleSwivel(index,parentQ,upperQ,axis,currentPole,desiredPole){
  if(diagnose(index,parentQ,upperQ).withinLimits)return 0;
  const j=joints[index],left=qinv(qm(parentQ,j.c1)),right=qm(upperQ,j.c2);
  // q(t)=q0*cos(t/2)+q1*sin(t/2). With u=tan(t/2), each
  // quaternion component is linear in u, up to a common normalization.
  const q0=qm(left,right),q1=qm(qm(left,[...axis,0]),right);
  const c=q0.map((x,i)=>[x,q1[i]]),product=(a,b)=>polynomialProduct(c[a],c[b]);
  const xx=product(0,0),ww=product(3,3),norm=polynomialAdd(xx,ww);
  const y=polynomialAdd(product(3,1),product(0,2),-1),z=polynomialAdd(product(3,2),product(0,1));
  const swing=polynomialAdd(polynomialAdd(polynomialProduct(y,y).map(x=>x/(j.sinY*j.sinY)),polynomialProduct(z,z).map(x=>x/(j.sinZ*j.sinZ))),polynomialProduct(norm,[1,0,1]),-1);
  const sin=Math.sin(j.twist/2),cos=Math.cos(j.twist/2),twist=polynomialAdd(xx.map(x=>x*cos*cos),ww.map(x=>x*sin*sin),-1);
  const roots=[...realRoots(swing),...realRoots(twist)].map(x=>2*Math.atan(x));
  const cuts=[-Math.PI,...roots.sort((a,b)=>a-b).filter((x,i,a)=>!i||x-a[i-1]>1e-10),Math.PI];
  const valid=t=>diagnose(index,parentQ,qm(qexp(mul(axis,t)),upperQ)).withinLimits;
  const prior=unit(orthogonal(currentPole,axis));
  let best=null,bestDistance=Infinity,bestPrior=-Infinity;
  for(let i=1;i<cuts.length;i++){
   const lo=cuts[i-1],hi=cuts[i],mid=(lo+hi)*.5;if(!valid(mid))continue;
   let t=clamp(0,lo,hi);
   if(!valid(t)){
    // Excludes the undefined twist point at exactly 180 degrees of swing.
    let bad=t,good=mid;for(let k=0;k<40;k++){const m=(bad+good)*.5;if(valid(m))good=m;else bad=m;}t=good;
   }
   const distance=Math.abs(t),continuity=dot(prior,rotate(qexp(mul(axis,t)),desiredPole));
   if(distance<bestDistance-1e-8||(Math.abs(distance-bestDistance)<1e-8&&continuity>bestPrior)){best=t;bestDistance=distance;bestPrior=continuity;}
  }
  // Some hand targets are incompatible with this shoulder cone at every elbow
  // swivel. Preserve reach and the true elbow hinge; callers can inspect the
  // shoulder diagnostic rather than silently moving the contact target.
  return best===null?0:best;
 }
 // Mutates only the three arm joints. Pole is a world-space bend direction,
 // projected off the shoulder-to-target axis. Segment lengths come from the input pose. Shoulder
 // orientation uses the nearest feasible pole swivel; the elbow has one DOF and the
 // requested wrist orientation is projected into its Jolt cone afterward.
 function solveArm(pose,side,target,pole,handQ){
  const a=arms[side==='left'?'l':side==='right'?'r':side];if(!a)throw Error('Unknown slide arm: '+side);
  const {upper,lower,hand,j}=a,start=pose.points[upper];
  const l1=length(sub(pose.points[lower],start)),l2=length(sub(pose.points[hand],pose.points[lower]));
  if(l1<1e-8||l2<1e-8)return pose;
  const offset=sub(target,start),distance=length(offset);
  const axis=distance>1e-8?mul(offset,1/distance):unit(sub(pose.points[hand],start));
  const near=Math.sqrt(Math.max(0,l1*l1+l2*l2+2*l1*l2*Math.cos(j.max)));
  const d=clamp(distance,Math.max(1e-7,near),l1+l2),bend=Math.acos(clamp((d*d-l1*l1-l2*l2)/(2*l1*l2),-1,1));
  let p=orthogonal(pole||sub(pose.points[lower],start),axis);
  if(length(p)<1e-8)p=orthogonal(sub(pose.points[lower],start),axis);
  p=length(p)>1e-8?unit(p):perpendicular(axis);
  const along=(l1*l1-l2*l2+d*d)/(2*d),height=Math.sqrt(Math.max(0,l1*l1-along*along));
  let elbow=add(start,add(mul(axis,along),mul(p,height))),upperDir=unit(sub(elbow,start));
  const normal=unit(mul(cross(axis,p),-1));
  let upperQ=unit(qm(fromAxes([upperDir,normal,cross(upperDir,normal)]),a.basisToBody));
  const swivel=feasibleSwivel(upper,pose.q[parents[upper]],upperQ,axis,sub(pose.points[lower],start),p);
  if(Math.abs(swivel)>1e-12){const turn=qexp(mul(axis,swivel));p=rotate(turn,p);elbow=add(start,add(mul(axis,along),mul(p,height)));upperQ=unit(qm(turn,upperQ));}
  pose.q[upper]=upperQ;
  pose.q[lower]=unit(qm(pose.q[upper],hingeRelative(j,bend)));
  const desiredHandQ=handQ||qm(pose.q[lower],joints[hand].refRelative);
  pose.q[hand]=project(hand,pose.q[lower],desiredHandQ,false).q;
  pose.points[lower]=elbow;
  pose.points[hand]=add(elbow,mul(rotate(pose.q[lower],a.forearmDirection),l2));
  if(!pose.axes)pose.axes=pose.q.map(toAxes);
  else for(const i of [upper,lower,hand])pose.axes[i]=toAxes(pose.q[i]);
  return pose;
 }
 return {reference,joints,arms,project,diagnose,solveArm,hingeRelative,feasibleSwivel,blendLocal};
}
const api={build};
if(typeof module==='object'&&module.exports)module.exports=api;else root.SlideJoints=api;
})(typeof globalThis!=='undefined'?globalThis:this);
