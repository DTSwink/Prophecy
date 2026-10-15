'use strict';
const $=id=>document.getElementById(id),R=Recovery,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),posAt=(d,j)=>d.points[j],axisAt=(d,j,a)=>d.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,dataset=null,filter='all',page=0,selected=null,time=0,playing=true,last=0,slots=[];
const cameraDefault={yaw:-.65,pitch:-.15,zoom:1.3,panX:0,panY:0},cameraState={...cameraDefault};
function resetCamera(){Object.assign(cameraState,cameraDefault);drawAll()}
function visible(){return dataset.clips.filter(c=>filter==='all'||c.gait===filter)}
function setPlaying(p){playing=p;$('play').textContent=p?'Pause':'Play'}
function displayPoint(p,shift){return [(p[0]-shift[0])*.01,p[2]*.01,(p[1]-shift[1])*.01]}
// Shared renderer expects local X,-Y,Z, with world Y/Z swapped for display.
function axes(q){return [[1,0,0],[0,1,0],[0,0,1]].map((v,k)=>{const a=R.rotate(q,v);return [a[0],a[2],a[1]].map(x=>k===1?-x:x)})}
function bounds(c){return $('bestCuts').checked&&c.cut?[c.cut.start,c.cut.end]:[0,c.frames.length-1]}
function duration(c){const [a,b]=bounds(c);return (b-a)/60}
function timelineDuration(){const list=slots.filter(s=>s.clip).map(s=>duration(s.clip));return list.length?Math.max(...list):3}
function poseAt(c){const [start,end]=bounds(c),d=duration(c),local=time<=d?time:time%d;let t=clamp(start+local*60,start,end),i=Math.floor(t),u=t-i,a=c.frames[i],b=c.frames[Math.min(i+1,end)];return a.map((p,j)=>[...p.slice(0,3).map((x,k)=>x+(b[j][k]-x)*u),...R.qslerp(p.slice(3),b[j].slice(3),u)])}
function drawAll(){
 if(!dataset)return;
 for(const slot of slots){if(!slot.clip)continue;const pose=poseAt(slot.clip),shift=pose[0];slot.renderer.draw({points:pose.map(p=>displayPoint(p,shift)),axes:pose.map(p=>axes(p.slice(3))),tint:slot.clip.gait==='walk'?[.97,.59,.27]:[.91,.49,.25],bicolor:$('bicolor').checked,skeleton:$('skeleton').checked,hideSword:true,upperOnly:false},[0,0,0]);}
 const d=timelineDuration(),shown=time<=d?time:time%d;$('clock').textContent=shown.toFixed(2)+' / '+d.toFixed(2)+' s';$('timeline').max=Math.round(d*60);$('timeline').value=Math.round(shown*60);
}
function show(){
 const all=visible();page=clamp(page,0,Math.max(0,Math.ceil(all.length/6)-1));
 const list=selected?[dataset.clips.find(c=>c.id===selected)]:all.slice(page*6,page*6+6);
 $('grid').classList.toggle('single',!!selected);$('rangeInfo').textContent=selected?'Single recording':`${all.length? page*6+1:0}–${Math.min((page+1)*6,all.length)} / ${all.length}`;
 $('prevPage').disabled=!!selected||page===0;$('nextPage').disabled=!!selected||(page+1)*6>=all.length;
 slots.forEach((s,i)=>{const c=list[i];s.clip=c||null;s.card.hidden=!c;if(c){s.title.textContent=c.label;const cut=$('bestCuts').checked&&c.cut;s.metrics.textContent=cut?`Ticks ${cut.start}–${cut.end} · ${cut.duration.toFixed(3)} s${cut.warning?' · Check seam':''}`:`${c.gait.toUpperCase()} · Input ${c.speed.toFixed(1)} cm/s · 181 samples`;s.metrics.style.color=cut&&cut.warning?'#ffb273':'';s.metrics.title=`Source clip ${c.sourceSpeed.toFixed(2)} cm/s; native direction limit ${c.capSpeed.toFixed(2)} cm/s`+(cut?` · Seam: ${cut.metrics.position_rms_cm.toFixed(2)} cm RMS / ${cut.metrics.rotation_rms_deg.toFixed(2)}° RMS. No blending.`:'');s.focus.textContent=selected?'Grid':'Expand';s.focus.onclick=()=>{selected=selected?null:c.id;time=0;$('clips').value=selected||'';show()}}});
 requestAnimationFrame(drawAll);
}
async function load(){try{dataset=await(await fetch('/data.json')).json();names=dataset.names;parents=dataset.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));$('clips').replaceChildren(new Option('Choose a recording…',''),...dataset.clips.map(c=>new Option(c.label,c.id)));show();$('error').hidden=true}catch(e){$('error').textContent=String(e);$('error').hidden=false;}}
for(let i=0;i<6;i++){const card=document.createElement('article');card.className='card';card.innerHTML='<header><strong></strong><button>Expand</button></header><canvas></canvas><div class="metrics"></div>';$('grid').append(card);slots.push({card,title:card.querySelector('strong'),focus:card.querySelector('button'),metrics:card.querySelector('.metrics'),renderer:new WebGLMotionRenderer(card.querySelector('canvas'),{pixelRatio:Math.min(devicePixelRatio,1.5)})})}
for(const id of ['all','walk','run'])$(id).onclick=()=>{filter=id;page=0;selected=null;time=0;$('clips').value='';for(const k of ['all','walk','run'])$(k).classList.toggle('active',k===id);show()};
$('clips').onchange=()=>{selected=$('clips').value||null;time=0;show()};$('gridMode').onclick=()=>{selected=null;time=0;$('clips').value='';show()};$('prevPage').onclick=()=>{page--;time=0;show()};$('nextPage').onclick=()=>{page++;time=0;show()};$('play').onclick=()=>setPlaying(!playing);$('timeline').oninput=()=>{time=Number($('timeline').value)/60;drawAll()};$('prevFrame').onclick=()=>{setPlaying(false);time=clamp((Math.round((time<=timelineDuration()?time:time%timelineDuration())*60)-1)/60,0,timelineDuration());drawAll()};$('nextFrame').onclick=()=>{setPlaying(false);time=clamp((Math.round((time<=timelineDuration()?time:time%timelineDuration())*60)+1)/60,0,timelineDuration());drawAll()};$('resetCamera').onclick=resetCamera;$('reload').onclick=load;$('bicolor').onchange=drawAll;$('skeleton').onchange=drawAll;$('bestCuts').onchange=()=>{time=0;show()};
window.addEventListener('keydown',e=>{if(/INPUT|SELECT/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();setPlaying(!playing)}if(e.code==='ArrowLeft'||e.code==='ArrowRight'){e.preventDefault();$(e.code==='ArrowLeft'?'prevFrame':'nextFrame').click()}},true);
function frame(now){if(last&&playing){time+=(now-last)*.001*Number($('speed').value);if(time>timelineDuration()&&!$('loop').checked){time=timelineDuration();setPlaying(false)}drawAll()}last=now;requestAnimationFrame(frame)}
load();requestAnimationFrame(frame);
