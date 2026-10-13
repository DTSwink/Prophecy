const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),Tip=require('./tipalign');
const setup=require('./data/unreal-setup.json'),tip=H.bladeTip(setup),holster={p:[0,0,0],q:[0,0,0,1],s:[1,1,1]};
let cases=0;
for(const distance of [0,1,50])for(const degrees of [0,2,60]){
 const dock={tick:10,local:{q:[0,0,0,1]},endQ:R.qexp([0,0,degrees*Math.PI/180]),startHand:[0,0,0],endHand:[distance,0,0],scale:.8,
  translationTicks:distance/230*60,rotationTicks:degrees/600*60};
 dock.ticks=Math.max(1,Math.ceil(Math.max(dock.translationTicks,dock.rotationTicks)));
 for(let t=0;t<=dock.ticks+.1;t+=.03125){
  const f=Tip.sample(H,setup,tip,dock,holster,dock.tick+t),p=f.goal.p;
  assert(Math.abs(p[0]-Math.min(distance,230*t/60))<1e-8,'translation runs at230 until arrival');
  assert(Math.abs(H.angle([0,0,0,1],f.sword.q)-Math.min(degrees,600*t/60))<1e-4,'rotation runs at600 until arrival');
 }
 cases++;
}
console.log(JSON.stringify({cases,translationCmPerSec:230,rotationDegPerSec:600,independentArrival:true}));
