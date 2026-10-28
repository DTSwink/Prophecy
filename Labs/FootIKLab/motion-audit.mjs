import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {parseArgs} from 'node:util';
const require=createRequire(import.meta.url),{audit}=require('./motion-audit.js');

// Self-contained SVG report, drawn only on user input. No WebGL, server or loop.
export function renderReport(report){
 const data=JSON.stringify(report).replace(/</g,'\\u003c');
 return String.raw`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Foot IK motion audit</title>
<style>:root{color-scheme:dark;font:14px system-ui;background:#121821;color:#e5eaf2}body{margin:20px;max-width:1400px}h1{font-size:20px;margin-bottom:4px}p{color:#a7b7ce;max-width:1000px}button,input,select{font:inherit;background:#243249;color:inherit;border:1px solid #4c5d78;border-radius:5px;padding:6px}button{cursor:pointer}input[type=range]{width:min(45vw,600px)}.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:12px 0}.views{display:grid;grid-template-columns:1fr 1fr;gap:10px}.view{width:100%;height:380px;background:#18212e;border:1px solid #39465b}.metric{width:100%;height:160px;background:#18212e}.legend{color:#f6a65e}.raw{color:#a998eb}.dim{color:#9db0c7}table{border-collapse:collapse;font-size:12px;width:100%}th,td{text-align:left;padding:7px;border-bottom:1px solid #304157}tbody tr{cursor:pointer}tbody tr:hover{background:#243249}#values{white-space:pre-line;font:12px ui-monospace;line-height:1.5;margin:10px 0}.label{fill:#abb9cd;font:12px system-ui}@media(max-width:800px){.views{grid-template-columns:1fr}.view{height:330px}}</style>
<h1>Foot IK · motion audit</h1><p>Review candidates, not an automatic verdict. <span class="legend">Orange = corrected</span>; <span class="raw">purple = same-frame NN</span>. Shoe boxes use the actual contact geometry. Native samples retain half-frame detail; frame numbers use60Hz.</p>
<div class="bar"><button id="prev">←</button><input id="seek" type="range" min="0" step="1"><button id="next">→</button><label>Frame <input id="frame" type="number" min="0" step="0.5" style="width:80px"></label><label><input id="local" type="checkbox"> Pelvis follow</label><label><input id="trail" type="checkbox" checked> Foot trails</label></div>
<div class="views"><svg id="side" class="view" viewBox="0 0 600 380" role="img" aria-label="Side motion inspection"></svg><svg id="front" class="view" viewBox="0 0 600 380" role="img" aria-label="Front motion inspection"></svg></div>
<div id="values"></div><div class="bar"><label>Trace <select id="metric"></select></label><label>Foot <select id="foot"><option value="0">Left</option><option value="1">Right</option></select></label></div><svg id="plot" class="metric" viewBox="0 0 1200 160"></svg>
<details><summary>Provenance and limits</summary><pre id="meta" style="white-space:pre-wrap"></pre></details>
<h2 style="font-size:16px">Ranked review intervals</h2><table><thead><tr><th>Metric</th><th>Foot</th><th>Frames</th><th>Peak</th><th>Interpretation</th></tr></thead><tbody id="worst"></tbody></table>
<script>const D=${data};
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg',el=(tag,attrs,text)=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;},fmt=(v,n=3)=>v===null||v===undefined?'—':Number(v).toFixed(n),add=(a,b)=>a.map((v,i)=>v+b[i]),mul=(a,s)=>a.map(v=>v*s),edges=[[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]],g=D.geometry,rows=D.rows;
let current=0;$('seek').max=rows.length-1;$('frame').max=rows.at(-1).frame;
const metricPairs={speed:'nnSpeed',normalSpeed:null,pelvisProgress:'nnPelvisProgress',acceleration:'nnAcceleration',accelerationExtra:null,kneePoleStep:'nnKneePoleStep',ankleNNError:null,footStep:'nnFootStep',pinError:null,pinSlip:null,soleGap:'nnSoleGap',reach:null};
for(const k of Object.keys(metricPairs)){const o=document.createElement('option');o.value=k;o.textContent=k;$('metric').append(o);}
$('meta').textContent=JSON.stringify({metadata:D.metadata,summary:D.summary},null,2);
for(const w of D.worstIntervals){const tr=document.createElement('tr');for(const value of [w.metric,w.side||'—',w.start+'–'+w.end,fmt(w.peak),w.note||'Inspect against source and adjacent frames']){const td=document.createElement('td');td.textContent=value;tr.append(td);}tr.onclick=()=>setFrame(Math.round(w.peakFrame*D.metadata.fps/D.metadata.userFps));$('worst').append(tr);}
function drawView(id,hAxis,label){const svg=$(id);svg.replaceChildren();if(!g)return;const f=g.frames[current],pelvis=g.names.indexOf('pelvis'),center=$('local').checked?f.points[pelvis]:f.points[0],scale=145,project=p=>[300+(p[hAxis]-center[hAxis])*scale,325-(p[1]-center[1])*scale];
 const line=(a,b,color,width,opacity=1)=>{const x=project(a),y=project(b);svg.append(el('line',{x1:x[0],y1:x[1],x2:y[0],y2:y[1],stroke:color,'stroke-width':width,opacity}));};
 for(const s of g.surfaces){const [a,b,c,d]=s.bounds,pts=[[a,c],[a,d],[b,d],[b,c]].map(([u,v])=>add(s.origin,add(mul(s.u,u),mul(s.v,v))));svg.append(el('polygon',{points:pts.map(p=>project(p).join(',')).join(' '),fill:'#2c4055',stroke:'#5c7795','stroke-width':1,opacity:.6}));}
 if($('trail').checked)for(let side=0;side<2;side++){const bone=g.names.indexOf('foot_'+(side?'r':'l'));for(const raw of [true,false]){const points=g.frames.slice(Math.max(0,current-14),Math.min(rows.length,current+15)).map(q=>project(q[raw?'raw':'points'][bone]).join(','));svg.append(el('polyline',{points:points.join(' '),fill:'none',stroke:raw?'#b29cdf':side?'#f6a65e':'#61d6df',opacity:.5,'stroke-width':1.3,'stroke-dasharray':raw?'3 3':''}));}}
 for(const raw of [true,false]){const points=f[raw?'raw':'points'],color=raw?'#a998eb':'#f6a65e';for(let j=1;j<points.length;j++)if(g.parents[j]>=0)line(points[j],points[g.parents[j]],color,raw?3:4,raw?.55:1);for(const shoe of f[raw?'rawShoes':'shoes'])for(let b=0;b<shoe.length;b+=8)for(const[a,c]of edges)line(shoe[b+a],shoe[b+c],color,raw?1:1.5,raw?.4:1);}
 for(const p of f.contacts)if(p){const v=project(p);svg.append(el('circle',{cx:v[0],cy:v[1],r:4,fill:'none',stroke:'#61f2b1','stroke-width':2}));}
 svg.append(el('text',{x:14,y:22,class:'label'},label+' · '+rows[current].frame));}
function drawPlot(){const svg=$('plot');svg.replaceChildren();const key=$('metric').value,reference=metricPairs[key],side=+$('foot').value,values=rows.flatMap(r=>[r.feet[side][key],reference?r.feet[side][reference]:null]).filter(v=>Number.isFinite(v));let lo=Math.min(0,...values),hi=Math.max(.001,...values);const xy=(v,i)=>[50+i/(rows.length-1)*1130,135-(v-lo)/(hi-lo)*110];
 for(const [name,color]of [[reference,'#a998eb'],[key,'#f6a65e']])if(name){let segment=[];const flush=()=>{if(segment.length)svg.append(el('polyline',{points:segment.join(' '),fill:'none',stroke:color,'stroke-width':1.5}));segment=[];};rows.forEach((r,i)=>{const v=r.feet[side][name];if(Number.isFinite(v))segment.push(xy(v,i).join(','));else flush();});flush();}
 const x=xy(0,current)[0];svg.append(el('line',{x1:x,y1:20,x2:x,y2:140,stroke:'#edf3fa','stroke-width':1}));svg.append(el('text',{x:5,y:25,class:'label'},fmt(hi,2)));svg.append(el('text',{x:5,y:140,class:'label'},fmt(lo,2)));svg.append(el('text',{x:55,y:155,class:'label'},'0'));svg.append(el('text',{x:1130,y:155,class:'label'},rows.at(-1).frame));svg.onclick=e=>{const box=svg.getBoundingClientRect();setFrame(Math.round(((e.clientX-box.left)/box.width*1200-50)/1130*(rows.length-1)));};}
function setFrame(i){current=Math.max(0,Math.min(rows.length-1,i));$('seek').value=current;$('frame').value=rows[current].frame;const r=rows[current];$('values').textContent='Frame '+r.frame+' · '+fmt(r.time)+' s · root '+fmt(r.rootSpeed)+' m/s · bone difference vs NN '+fmt(r.boneLengthError*1000,3)+' mm\n'+r.feet.map((f,i)=>(i?'R':'L')+' '+f.state+' | gap '+fmt(f.soleGap===null?null:f.soleGap*100,2)+' cm | material pin error '+fmt(f.pinError===null?null:f.pinError*1000,3)+' mm | ankle vs NN '+fmt(f.ankleNNError,1)+'° | pelvis travel '+fmt(f.pelvisProgress)+' m/s | knee step '+fmt(f.kneePoleStep,1)+'°').join('\n');drawView('side',2,'Side Z/Y');drawView('front',0,'Front X/Y');drawPlot();}
$('prev').onclick=()=>setFrame(current-2);$('next').onclick=()=>setFrame(current+2);$('seek').oninput=e=>setFrame(+e.target.value);$('frame').oninput=e=>setFrame(Math.round(+e.target.value*D.metadata.fps/D.metadata.userFps));for(const id of ['local','trail','metric','foot'])$(id).onchange=()=>setFrame(current);document.addEventListener('keydown',e=>{if(['INPUT','SELECT'].includes(e.target.tagName))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setFrame(current+(e.key==='ArrowLeft'?-2:2));}});setFrame(0);
</script></html>`;
}

export function writeReport(report,out){
 const stem=out.replace(/\.(html|json)$/i,'');fs.mkdirSync(path.dirname(stem),{recursive:true});
 fs.writeFileSync(stem+'.json',JSON.stringify(report));fs.writeFileSync(stem+'.html',renderReport(report));
 return {json:stem+'.json',html:stem+'.html'};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const {values:v}=parseArgs({options:{input:{type:'string'},out:{type:'string'},gait:{type:'string',default:'walk'},phase:{type:'string',default:'.21'},terrain:{type:'string',default:'stairs'},height:{type:'string',default:'16'},depth:{type:'string',default:'35'},steps:{type:'string',default:'12'},clearance:{type:'string',default:'1'}}});
 let fixture;
 if(v.input)fixture=JSON.parse(fs.readFileSync(v.input,'utf8'));
 else{const K=require('./footik.js'),{load}=require('./test-bank.cjs'),run=load(v.gait,+v.phase);fixture={run,model:K.prepare(run,{gait:v.gait,phase:+v.phase,terrain:v.terrain,height:+v.height,depth:+v.depth,steps:+v.steps,clearance:+v.clearance})};}
 const report=audit(fixture),out=v.out||fileURLToPath(new URL('snapshots/motion-audit-'+v.gait,import.meta.url)),files=writeReport(report,out);
 console.log(JSON.stringify({files,summary:report.summary,worstIntervals:report.worstIntervals.slice(0,8)}));
}
