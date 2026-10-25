import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const baseline=JSON.parse(fs.readFileSync(new URL('data/height-budget-before.json',import.meta.url))),run=load('walk',baseline.phase),started=performance.now(),m=K.prepare(run),prepareMs=performance.now()-started,j=run.names.indexOf('foot_r'),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const sample=n=>m.sample(n/60),old=n=>baseline.rows[n*2];
const f=sample(161),extra=f.pose.points[j][1]-f.raw.points[j][1],beforeExtra=old(161).p[1]-old(161).nn[1];
// Earlier authored toe-off changes this phase alignment; retain a real
// reduction without demanding the old low arc that caused abrupt braking.
check('161 still reduces unnecessary NN-relative lift',extra<beforeExtra);
check('161 shoe gap remains below 20cm without floor clipping',f.feet[1].soleGap<.20&&f.feet[1].soleGap>0);
const velocity=(rows,i)=>R.mul(R.sub(rows[i].p,rows[i-1].p),120);
const rows=m.frames.map(f=>({p:f.pose.points[j]}));
check('Earlier departure reduces the old frame158 lift speed',velocity(rows,316)[1]<velocity(baseline.rows,316)[1]);
check('159-167 continues forward and upward without a new stall',Array.from({length:17},(_,i)=>velocity(rows,318+i)).every(v=>v[1]>.2&&v[2]>1));
const peak=xs=>Math.max(...Array.from({length:60},(_,n)=>{const i=315+n;return R.length(R.sub(velocity(xs,i),velocity(xs,i-1)));}));
check('Height reduction does not increase the release-window velocity kick',peak(rows)<=peak(baseline.rows)+1e-4);
check('Whole-course shoes retain collision clearance',m.metrics.maxPenetration<1e-5);
check('Whole-course leg targets remain reachable',m.metrics.maxReachError<1e-5);
check('Flat NN frames stay exact',m.frames.filter(f=>!f.influence).every(f=>JSON.stringify(f.pose)===JSON.stringify(f.raw)));
const result={passed:true,checks,prepareMs,frame161:{gapBeforeCm:old(161).gap*100,gapAfterCm:f.feet[1].soleGap*100,extraBeforeCm:beforeExtra*100,extraAfterCm:extra*100},releaseKickBefore:peak(baseline.rows),releaseKickAfter:peak(rows)};
fs.writeFileSync(new URL('height-budget-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
