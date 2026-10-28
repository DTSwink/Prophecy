import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {renderReport} from './motion-audit.mjs';
const require=createRequire(import.meta.url),{audit,signedShoeGap}=require('./motion-audit.js'),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
const run=load('walk',.21),flat=K.prepare(run,{terrain:'flat'}),base=audit({run,model:flat,options:{geometry:false}});
check('Report retains native120Hz with user60Hz frame numbering',base.rows[1].frame===.5&&base.rows[120].frame===60&&base.metadata.fps===120);
check('Same NN source has exact zero joint/articulation differences',base.summary.root.boneLengthError.value===0&&base.summary.L.ankleNNError.value<.00001&&base.summary.R.ankleNNError.value<.00001);
check('Native NN acceleration and angular boundaries are not invented corrections',base.summary.L.accelerationExtra.value===0&&base.summary.L.footStepExtra.value===0&&base.summary.R.kneePoleExtra.value===0);
check('Constant commanded root speed does not gain a startup acceleration spike',base.rows[1].rootAcceleration<.0001);
const seed=flat.frames[30].pose,l=S.leg(seed,run.names,'L'),localPoint=[0,-.10,.02],contactPoint=R.add(seed.points[l.foot],R.rotate(seed.q[l.foot],localPoint));
function fixture(moving=false,drift=false){const frames=[];for(let i=0;i<8;i++){
 const p=structuredClone(seed),delta=R.qexp([0,i*.08,0]),q=R.qm(delta,seed.q[l.foot]),shift=moving?[i*.01,0,0]:[0,0,0],destination=R.add(contactPoint,shift);
 p.q[l.foot]=q;p.q[l.toe]=R.qm(delta,seed.q[l.toe]);p.points[l.foot]=R.sub(destination,R.rotate(q,localPoint));if(drift)p.points[l.foot][0]+=i*.003;
 p.points[l.toe]=R.add(p.points[l.foot],R.rotate(q,l.toeLocal));p.axes=p.q.map(R.toAxes);
 frames.push({pose:p,raw:seed,feet:[{state:'ROLL',contact:{point:destination,localPoint,surface:'floor',stanceId:1,normal:[0,1,0]}},{state:'SWING',contact:null}]});}
 return {run,model:{fps:120,frames,terrain:{surfaces:[S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-10,10,-10,10])]}},options:{geometry:false}};
}
const rolling=audit(fixture());
check('Legitimate heel-toe pivot rotation is not measured as pin slip',rolling.summary.L.pinError.value===0&&rolling.summary.L.pinSlip.value===0&&rolling.summary.L.speed.value>0);
const moving=audit(fixture(true));
check('Material contact follows moving-platform destination without false slip',moving.summary.L.pinError.value===0&&moving.summary.L.pinSlip.value===0);
const drift=audit(fixture(false,true));
check('Actual3mm-per-sample material drift is detected',Math.abs(drift.summary.L.pinError.value-.021)<1e-8&&Math.abs(drift.summary.L.pinSlip.value-.36)<1e-8);
const box=[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>[x,y,z]))),surface={id:'tiny',origin:[0,0,0],u:[1,0,0],v:[0,0,1],normal:[0,1,0],bounds:[-.1,.1,-.1,.1]};
check('Full face clipping detects penetration when no box corner lies over tread',Math.abs(signedShoeGap(box,[surface]).gap+1)<1e-9);
for(const degrees of [45,90]){const q=R.qexp([degrees*Math.PI/180,0,0]),rot=v=>R.rotate(q,v),s={...surface,origin:rot(surface.origin),u:rot(surface.u),v:rot(surface.v),normal:rot(surface.normal)};
 check('Whole-shoe clearance is surface-normal aware at'+degrees+'degrees',Math.abs(signedShoeGap(box.map(rot),[s]).gap+1)<1e-9);
}
const invalid={...fixture(),model:{fps:120,frames:fixture().model.frames}};
check('Missing terrain is disclosed as unverified instead of asserted safe',audit(invalid).metadata.surfaceCoverage.startsWith('none'));
const kneeFixture=fixture();kneeFixture.model.frames.forEach(f=>{f.pose=structuredClone(seed);f.raw=structuredClone(seed);f.feet=[{state:'SWING'},{state:'SWING'}];});
const axis=R.unit(R.sub(seed.points[l.foot],seed.points[l.hip])),turn=R.qexp(R.mul(axis,Math.PI*.5));
kneeFixture.model.frames[4].pose.points[l.knee]=R.add(seed.points[l.hip],R.rotate(turn,R.sub(seed.points[l.knee],seed.points[l.hip])));
const kneeResult=audit(kneeFixture);
check('Injected knee-pole90degree flip is distinguished from unchanged NN',kneeResult.summary.L.kneePoleExtra.value>89);
const stallFixture=fixture();stallFixture.model.frames=Array.from({length:32},(_,i)=>{const p=structuredClone(seed);for(let j=0;j<p.points.length;j++)if(j!==l.foot&&j!==l.toe)p.points[j][2]+=.01*i;return{pose:p,raw:p,feet:[{state:'SWING'},{state:'SWING'}]};});
const stalled=audit(stallFixture);
check('Sustained pelvis-relative backward swing is surfaced without calling NN invalid',stalled.worstIntervals.some(w=>w.kind==='possible-swing-stall'&&w.side==='L'&&w.duration>.1&&w.note.includes('valid rear-leg')));
const report=audit({run,model:flat}),html=renderReport(report);
check('Standalone SVG report contains material shoe geometry and both source traces',html.includes('rawShoes')&&html.includes('Ranked review intervals')&&report.geometry.frames[0].shoes[0].length===16);
check('Exported report script parses independently of the generator',!!new vm.Script(html.match(/<script>([\s\S]*)<\/script>/)[1]));
const result={passed:true,checks,measurements:{flatNN:base.summary,materialDrift:drift.summary.L.pinError,rotatingPin:rolling.summary.L.pinError,kneeFlip:kneeResult.summary.L.kneePoleExtra}};
fs.writeFileSync(new URL('motion-audit-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,checks:checks.length}));
