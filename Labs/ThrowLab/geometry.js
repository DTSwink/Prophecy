// Bodyflip support.js footFrame, unchanged; geometry only, no solver.
const BodyflipSupport=(()=>{const {sub,mul,dot,cross,unit}=Recovery;
function footFrame(p,ankle,toe,side){
 const a=p.axes[ankle],b=p.axes[toe],delta=sub(p.points[toe],p.points[ankle]),sign=side==='L'?1:-1;
 const forward=mul(a[1],dot(a[1],delta)<0?-1:1),up=mul(a[0],sign);
 const tf=mul(b[0],dot(b[0],forward)<0?-1:1),tu=mul(b[1],sign),ts=unit(cross(tf,tu));
 return {forward,up,side:a[2],toeForward:tf,toeUp:tu,toeSide:ts};
}
return {footFrame};})();
