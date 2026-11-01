import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),J=require('./jump-attack.js'),T=require('./throw-attack.js'),read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,ref=C.poseFromShared(m),manifest=read('data/vanilla.json'),policy=C.attackReturn(),rad=Math.PI/180;T.load(read('data/throws.json'));let checks=0;
const near=(a,b,label,tol=1e-8)=>{assert(Math.abs(a-b)<tol,label+': '+a+' / '+b);checks++;};
near(policy.factor(1/60),.9,'one tick removes ten percent');near(policy.factor(1/120)**2,.9,'120Hz agrees with 60Hz');near(policy.factor(.2),.9**12,'elapsed-time sampling');near(3*policy.factor(1/60)-3,3*(policy.factor(1/60)-1),'further angles move proportionally faster');assert.equal(policy.factor(1/60,.4*rad),0);checks++;
const slower=C.attackReturn({attackReturnLerp:.01}),faster=C.attackReturn({attackReturnLerp:.5});assert(slower.horizon>policy.horizon&&faster.horizon<policy.horizon);checks++;
near(C.attackReturn({attackReturnClockRate:2}).factor(.2),policy.factor(.1),'manual animation rate does not change real return response');
const snapSettings=C.sanitize({attackReturnLerp:.2,attackReturnSnap:1.3,bigThrowReturnFrames:7,smallThrowReturnFrames:9});for(const k of ['attackReturnLerp','attackReturnSnap','bigThrowReturnFrames','smallThrowReturnFrames'])near(C.sanitize(JSON.parse(JSON.stringify(snapSettings)))[k],snapSettings[k],'settings persist '+k);
// Nonlinear return is independent of sampling frequency and reaches the base.
for(const exponent of [0,.25,.5,.95,1]){
 const p=C.attackReturn({attackReturnExponent:exponent});let angle=2;
 for(let i=0;i<12;i++)angle*=p.factor(1/120,angle);
 near(angle,2*p.factor(.1,2),'power decay composes over elapsed time '+exponent);
 assert.equal(p.factor(p.horizon,Math.PI),0);checks++;
 near(C.attackReturn({attackReturnExponent:exponent,attackReturnClockRate:2}).factor(.2,2),p.factor(.1,2),'nonlinear real-time clock '+exponent);
}
const even=C.attackReturn({attackReturnExponent:.5});
assert(Math.PI*(1-even.factor(1/600,Math.PI))<Math.PI*(1-policy.factor(1/600,Math.PI)),'lower exponent softens large-angle speed');checks++;
assert(.1*(1-even.factor(1/600,.1))>.1*(1-policy.factor(1/600,.1)),'lower exponent speeds small-angle finish');checks++;
const linear=C.attackReturn({attackReturnExponent:0});near(2*(1-linear.factor(1/600,2)),.5*(1-linear.factor(1/600,.5)),'zero exponent gives constant angular speed');
near(C.sanitize({attackReturnExponent:.35}).attackReturnExponent,.35,'exponent persists');
const catalog=new Map();for(const id of ['slashL','jabR','KickL']){const meta=manifest.clips.find(c=>c.name===id),b=fs.readFileSync(new URL(meta.file,import.meta.url));catalog.set(id,C.decode(meta,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),names,parents));}
const base=()=>({pose:ref}),segment={sample:base,airStart:0,jumpStart:0,abortTime:Infinity},localRef=R.localize(ref.points,ref.q,parents),angles=p=>R.localize(p.points,p.q,parents).q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(localRef.q[i]))))),reports=[];
for(const id of ['slashL','jabR','KickL','big-throw','small-throw'])for(const direct of [false,true]){
 const settings=C.sanitize({kickToArmed:direct,motionCompensation:true,distributePelvisTurn:true}),track=J.create({attack:id},segment,catalog,names,parents,settings,ref),pose=t=>track.sample(t).pose,a=pose(track.end),b=pose(track.end+1/60),before=pose(track.end-1e-6),aa=angles(a),bb=angles(b);
 const continuity=Math.max(...a.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(before.q[i]))))));assert(continuity<.001,id+' continuous return boundary '+continuity);checks++;
 for(let i=0;i<aa.length;i++)near(bb[i],aa[i]*.9<=.5*rad?0:aa[i]*.9,id+' angular decay joint '+i,1e-7);
 const end=pose(track.returnEnd);near(Math.max(...angles(end)),0,id+' reaches base exactly');
 const seek=pose(track.end+.04);pose(track.end+.2);const again=pose(track.end+.04);near(Math.max(...seek.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(again.q[i])))))),0,id+' seek independent');
 reports.push({id,direct,continuity,returnHorizon:track.returnEnd-track.end});
}
for(const [id,frames] of [['big-throw',7],['small-throw',9]]){const track=T.create({attack:id},segment,null,names,parents,snapSettings,ref);near(track.end-track.releaseTime,frames/60,'per-throw return marker '+id);}
// The return follows a moving baseline, including translation and changing yaw.
const moving=t=>{const q=R.qexp([0,.4*t,0]);return {pose:{...ref,points:ref.points.map(p=>R.add(R.rotate(q,p),[t,.2*t,0])),q:ref.q.map(v=>R.qm(q,v))}};};
for(const id of ['slashL','KickL']){const track=J.create({attack:id},{...segment,sample:moving},catalog,names,parents,C.sanitize({kickToArmed:true,distributePelvisTurn:true}),ref);for(const t of [track.returnEnd,track.returnEnd+.3]){const p=track.sample(t).pose,b=moving(t).pose;near(Math.max(...p.points.map((v,i)=>R.length(R.sub(v,b.points[i])))),0,'moving baseline position reached');near(Math.max(...p.q.map((v,i)=>R.length(R.qlog(R.qm(v,R.qinv(b.q[i])))))),0,'moving baseline angles reached');}}
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),left=html.indexOf('</aside>'),more=html.indexOf('id="minorOptions"');for(const id of ['attackReturnLerp','attackReturnSnap','attackReturnExponent'])assert(html.indexOf('id="'+id+'"')<left);for(const id of ['bigThrowReturnFrames','smallThrowReturnFrames'])assert(html.indexOf('id="'+id+'"')>more);assert(!html.includes('id="jumpAttackOut"'));assert(/<input id="fallCap"[^>]*>\s*<section class="attack-return-controls">/.test(html),'return controls directly follow Fall cap');checks+=5;
fs.mkdirSync(new URL('../../Saved/BodyflipLab/AngularReturn/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/AngularReturn/results.json',import.meta.url),JSON.stringify({passed:true,checks,reports},null,2));console.log(JSON.stringify({passed:true,checks,cases:reports.length}));
