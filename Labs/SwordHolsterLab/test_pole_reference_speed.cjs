const assert=require('node:assert/strict'),P=require('./elbowpole.js'),R=require('./recovery.js');
let maxSpeed=0;
for(const hz of [60,240])for(const rate of [0,5,180]){
 let basis=null,angle=0;
 for(let i=0;i<=hz;i++){
  const t=i/hz,d=R.unit([-1,.2*Math.cos(t*Math.PI),.002*Math.sin(t*8*Math.PI)]),q=[0,0,0,1];
  const pose=[{p:[0,0,0],q},{p:R.add(R.mul(d,20),[0,0,5]),q},{p:R.mul(d,40),q},{p:[0,0,0],q}];
  const old=basis,oldAngle=angle;angle=P.advance(angle,40,rate*.4,1/hz);
  basis=P.frame(pose,[0,1,2],3,basis,Math.max(0,rate/hz-Math.abs(angle-oldAngle)));
  if(old){const previous=R.rotate(R.fromTo(old.d,basis.d),R.rotate(R.qexp(R.mul(old.d,oldAngle*Math.PI/180)),old.zero));
   const current=R.rotate(R.qexp(R.mul(basis.d,angle*Math.PI/180)),basis.zero);
   const speed=Math.acos(Math.max(-1,Math.min(1,R.dot(previous,current))))*180/Math.PI*hz;
   assert(speed<=rate+1e-3,`Reference plus preference exceed cap: ${speed} > ${rate}`);maxSpeed=Math.max(maxSpeed,speed);
  }
 }
}
console.log({passed:true,maxDegreesPerSecond:maxSpeed});
