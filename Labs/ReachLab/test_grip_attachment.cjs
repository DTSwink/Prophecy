const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const R=global.Recovery=require('../SwordHolsterLab/recovery.js');vm.runInThisContext(fs.readFileSync(path.join(__dirname,'grab.js'),'utf8'));
const G=ReachGrab,out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachGripFeedback20261016'),rows=JSON.parse(fs.readFileSync(path.join(out,'native-before.json'),'utf8')).rows;
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI,identity=[0,0,0,0,0,0,1],acquisitions=[];let maxPosition=0,maxQuaternion=0,cases=0;
for(let k=0;k<2;k++){
 const r=rows.find(r=>r.hands[k].gripped),h=r.hands[k],actual=G.relative(r.actualHands[k],r.space),goal=h.target,ball=h.ball;
 const desiredFromBall=G.relative(goal,ball),old=G.relative(ball,actual),fixed=G.attachment(ball,goal);
 const oldNext=G.compose(G.compose(goal,old),desiredFromBall);
 acquisitions.push({side:k,tick:r.tick,physicalAngle:angle(actual.slice(3),goal.slice(3)),physicalPosition:R.length(R.sub(actual.slice(0,3),goal.slice(0,3))),oldNextGoalAngle:angle(oldNext.slice(3),goal.slice(3)),oldNextGoalPosition:R.length(R.sub(oldNext.slice(0,3),goal.slice(0,3)))});
 // A consistent fixed relation gives no new command when either object/hand
 // moves. Cover common translations and arbitrary hand orientations.
 for(let i=0;i<120;i++){
  const wrist=[i*.7,-i*.2,95+i*.3,...R.qexp([Math.sin(i)*2,Math.cos(i*.3),Math.sin(i*.7)])],next=G.compose(G.compose(wrist,fixed),desiredFromBall);
  maxPosition=Math.max(maxPosition,R.length(R.sub(wrist.slice(0,3),next.slice(0,3))));maxQuaternion=Math.max(maxQuaternion,1-Math.abs(R.dot(wrist.slice(3),next.slice(3))));cases++;
 }
}
assert(maxPosition<1e-10&&maxQuaternion<1e-12);assert(acquisitions.every(a=>a.oldNextGoalAngle>.1));
const result={passed:true,cases,maxPosition,maxQuaternion,acquisitions};fs.writeFileSync(path.join(out,'attachment-invariant.json'),JSON.stringify(result,null,2));console.log(result);
