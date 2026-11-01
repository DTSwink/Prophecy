import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),J=require('./jump-attack.js'),T=require('./throw-attack.js'),read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,ref=C.poseFromShared(m),manifest=read('data/vanilla.json'),policy=C.attackReturn(),rad=Math.PI/180;T.load(read('data/throws.json'));let checks=0;
const near=(a,b,label,tol=1e-8)=>{assert(Math.abs(a-b)<tol,label+': '+a+' / '+b);checks++;};
const snapSettings=C.sanitize({bigThrowReturnFrames:7,smallThrowReturnFrames:9});
for(const duration of [.1,.25,.8]){const a=C.attackReturn({},duration),b=C.attackReturn({attackReturnLerp:1,attackReturnSnap:10,attackReturnExponent:0},duration);for(const t of [0,duration*.3,duration*.5,duration])near(a.factor(t),b.factor(t),'inactive sliders');near(a.factor(duration),0,'timed endpoint');}
const catalog=new Map();for(const id of ['slashL','jabR','KickL']){const meta=manifest.clips.find(c=>c.name===id),b=fs.readFileSync(new URL(meta.file,import.meta.url));catalog.set(id,C.decode(meta,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),names,parents));}
const base=()=>({pose:ref}),segment={sample:base,airStart:0,jumpStart:0,abortTime:Infinity},localRef=R.localize(ref.points,ref.q,parents),angles=p=>R.localize(p.points,p.q,parents).q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(localRef.q[i]))))),reports=[];
for(const id of ['slashL','jabR','KickL','big-throw','small-throw'])for(const direct of [false,true]){
 const settings=C.sanitize({kickToArmed:direct,motionCompensation:true,distributePelvisTurn:true}),track=J.create({attack:id},segment,catalog,names,parents,settings,ref),pose=t=>track.sample(t).pose,a=pose(track.end),b=pose(track.end+1/60),before=pose(track.end-1e-6),aa=angles(a),bb=angles(b);
 const continuity=Math.max(...a.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(before.q[i]))))));assert(continuity<.001,id+' continuous return boundary '+continuity);checks++;
 near(track.returnEnd-track.end,.25,id+' original duration');near(track.returnPolicy.factor(.125),.5,id+' timed aim midpoint');
 const end=pose(track.returnEnd);near(Math.max(...angles(end)),0,id+' reaches base exactly');
 const seek=pose(track.end+.04);pose(track.end+.2);const again=pose(track.end+.04);near(Math.max(...seek.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(again.q[i])))))),0,id+' seek independent');
 reports.push({id,direct,continuity,returnHorizon:track.returnEnd-track.end});
}
for(const [id,frames] of [['big-throw',7],['small-throw',9]]){const track=T.create({attack:id},segment,null,names,parents,snapSettings,ref);near(track.end-track.releaseTime,frames/60,'per-throw return marker '+id);}
// The return follows a moving baseline, including translation and changing yaw.
const moving=t=>{const q=R.qexp([0,.4*t,0]);return {pose:{...ref,points:ref.points.map(p=>R.add(R.rotate(q,p),[t,.2*t,0])),q:ref.q.map(v=>R.qm(q,v))}};};
for(const id of ['slashL','KickL']){const track=J.create({attack:id},{...segment,sample:moving},catalog,names,parents,C.sanitize({kickToArmed:true,distributePelvisTurn:true}),ref);for(const t of [track.returnEnd,track.returnEnd+.3]){const p=track.sample(t).pose,b=moving(t).pose;near(Math.max(...p.points.map((v,i)=>R.length(R.sub(v,b.points[i])))),0,'moving baseline position reached');near(Math.max(...p.q.map((v,i)=>R.length(R.qlog(R.qm(v,R.qinv(b.q[i])))))),0,'moving baseline angles reached');}}
// Duration selected from the start pose, then frozen across the whole return.
for(const w of [0,.5,1])for(const degrees of [45,90,180])near(C.returnDuration(.25,degrees*rad,w),.25*(1-w+w*degrees/90),'distance weight endpoints');
for(const id of ['slashL','KickL','big-throw','small-throw'])for(const weight of [.5,1]){
 const settings=C.sanitize({kickToArmed:true,distributePelvisTurn:true,attackReturnDistance:weight}),track=J.create({attack:id},segment,catalog,names,parents,settings,ref);
 near(track.returnEnd-track.end,C.returnDuration(.25,track.returnDistance,weight),id+' duration selected once');
 const fixed=J.create({attack:id},segment,catalog,names,parents,{...settings,attackReturnDistance:0},ref);for(const t of [track.start,track.hitTime,track.end]){const a=track.sample(t).pose,b=fixed.sample(t).pose;near(Math.max(...a.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(b.q[i])))))),0,id+' strike unchanged');}
 const duration=track.returnEnd-track.end,mid=track.sample(track.end+duration*.5).pose;
 track.sample(track.end-1);track.sample(track.returnEnd+1);const again=track.sample(track.end+duration*.5).pose;
 near(Math.max(...mid.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(again.q[i])))))),0,id+' scaled return seek independent');
 near(Math.max(...angles(track.sample(track.returnEnd).pose)),0,id+' scaled return reaches base');
 assert(!track.sample(track.returnEnd).attack,id+' attack ends at selected duration');checks++;
 const before=track.sample(track.end-1e-7).pose,after=track.sample(track.end+1e-7).pose;
 assert(Math.max(...before.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(after.q[i]))))))<.001,id+' scaled boundary continuity');checks++;
}
for(const id of ['slashL','KickL','big-throw','small-throw']){const track=J.create({attack:id,attackOut:.1},segment,catalog,names,parents,C.sanitize({attackReturnDuration:.6}),ref);near(track.returnEnd-track.end,.6,id+' global duration applies');}
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),left=html.indexOf('</aside>'),more=html.indexOf('id="minorOptions"');for(const id of ['attackReturnLerp','attackReturnSnap','attackReturnExponent'])assert(html.indexOf('id="'+id+'"')<left);for(const id of ['bigThrowReturnFrames','smallThrowReturnFrames'])assert(html.indexOf('id="'+id+'"')>more);assert(html.includes('id="attackReturnDuration"'));assert(/<input id="fallCap"[^>]*>\s*<section class="attack-return-controls">/.test(html),'return controls directly follow Fall cap');checks+=5;
fs.mkdirSync(new URL('../../Saved/BodyflipLab/DurationReturn/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/DurationReturn/results.json',import.meta.url),JSON.stringify({passed:true,checks,reports},null,2));console.log(JSON.stringify({passed:true,checks,cases:reports.length}));
