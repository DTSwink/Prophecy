/* Pointer-only editing leaves global playback keyboard shortcuts untouched. */
class RetimeEditor{
 constructor(host,title,onCommit){
  this.host=host;this.onCommit=onCommit;this.points=Retime.linear();this.active=-1;this.marker=null;
  host.className='retime-editor';host.innerHTML=`<div class="retime-heading"><strong>${title}</strong><button type="button">Linear</button></div><svg viewBox="0 0 280 160" aria-label="${title} retiming curve"><g class="curve-grid"></g><path class="curve-line"/><g class="curve-handles"></g><circle class="curve-marker" r="3"/></svg><div class="retime-axes"><span>Playback time →</span><span>↑ Motion progress</span></div>`;
  this.svg=host.querySelector('svg');this.path=host.querySelector('.curve-line');this.handles=host.querySelector('.curve-handles');this.dot=host.querySelector('.curve-marker');
  const grid=host.querySelector('.curve-grid');for(const v of [0,.25,.5,.75,1])grid.innerHTML+=`<path d="M${this.x(v)},10 V140 M20,${this.y(v)} H270"/>`;
  host.querySelector('button').onclick=()=>{this.set(Retime.linear());this.onCommit(this.points);};
  this.svg.addEventListener('pointerdown',e=>{const target=e.target.closest('[data-point]');if(!target)return;e.preventDefault();this.active=Number(target.dataset.point);this.svg.setPointerCapture(e.pointerId);});
  this.svg.addEventListener('pointermove',e=>{
   if(this.active<0)return;e.preventDefault();const rect=this.svg.getBoundingClientRect(),i=this.active;
   const x=((e.clientX-rect.left)/rect.width*280-20)/250,y=(140-(e.clientY-rect.top)/rect.height*160)/130;
   this.points[i]=[Math.max(i?this.points[i-1][0]+.01:.01,Math.min(i<3?this.points[i+1][0]-.01:.99,x)),Math.max(i?this.points[i-1][1]:0,Math.min(i<3?this.points[i+1][1]:1,y))];this.draw();
  });
  const finish=()=>{if(this.active<0)return;this.active=-1;this.onCommit(this.points.map(p=>[...p]));};
  this.svg.addEventListener('pointerup',finish);this.svg.addEventListener('pointercancel',finish);this.svg.addEventListener('lostpointercapture',finish);this.draw();
 }
 x(v){return 20+250*v;} y(v){return 140-130*v;}
 set(points){this.points=Retime.sanitize(points);this.draw();}
 draw(){
  const curve=Retime.prepare(this.points);this.path.setAttribute('d',Array.from({length:101},(_,i)=>`${i?'L':'M'}${this.x(i/100)},${this.y(Retime.sample(curve,i/100))}`).join(' '));
  this.handles.innerHTML=this.points.map((p,i)=>`<circle data-point="${i}" cx="${this.x(p[0])}" cy="${this.y(p[1])}" r="6"><title>Playback ${(p[0]*100).toFixed(0)}% → motion ${(p[1]*100).toFixed(0)}%</title></circle>`).join('');
  this.dot.style.display=this.marker===null?'none':'';if(this.marker!==null){this.dot.setAttribute('cx',this.x(this.marker));this.dot.setAttribute('cy',this.y(Retime.sample(curve,this.marker)));}
 }
 showProgress(value){this.marker=value;const curve=Retime.prepare(this.points);this.dot.style.display=value===null?'none':'';if(value!==null){this.dot.setAttribute('cx',this.x(value));this.dot.setAttribute('cy',this.y(Retime.sample(curve,value)));}}
}
