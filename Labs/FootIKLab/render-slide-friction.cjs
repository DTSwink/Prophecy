'use strict';
// Render saved stable-point slide measurements; no replay, inference, or browser.
const fs=require('fs'),path=require('path');
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
function render(before,after){
 const colors=['#f3a45a','#5dd2df','#b392f0'],width=1340,height=115+after.cases.length*550;
 const panels=[
  {title:'Ankle / palm height relative to root (m)',fields:[s=>s.foot_l?.[0],s=>s.foot_r?.[0],s=>s.palm?.[0]],labels:['Left ankle','Right ankle','Brace palm']},
  {title:'Knee bend (degrees)',fields:[s=>s.knee_l,s=>s.knee_r],labels:['Left knee','Right knee']},
  {title:'World root height (m)',fields:[s=>s.rootWorldY],labels:['Root — should coincide']},
  {title:'Upper torso rotation relative to root (degrees)',fields:[s=>s.spineRoot?.[0],s=>s.spineRoot?.[1],s=>s.spineRoot?.[2]],labels:['Axis X','Axis Y','Axis Z']},
  {title:'Hand height relative to shoulder (m)',fields:[s=>s.handShoulder_l?.[0],s=>s.handShoulder_r?.[0]],labels:['Left hand','Right hand']},
  {title:'Elbow bend (degrees)',fields:[s=>s.elbow_l,s=>s.elbow_r],labels:['Left elbow','Right elbow']}
 ];
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="${width}" height="${height}" fill="#101722"/><style>text{fill:#dbe5f1;font:11px sans-serif}.title{font-size:13px;font-weight:bold}.grid{stroke:#344052;stroke-width:1}.line{fill:none;stroke-width:1.8}</style><text x="24" y="25" class="title">Slide motion — stable ankle and palm points: solid candidate, dashed before</text><text x="24" y="45">Height follows the wall-up tangent. Dotted vertical line starts quality measurements; plotted motion begins at blend completion.</text><text x="24" y="63">Candidate ${escape(after.surfaceSha256)} · ${after.passed?'checks pass':'review failed checks'}</text>`;
 after.cases.forEach((candidate,row)=>{const original=before.cases.find(c=>c.threshold===candidate.threshold);if(!original)throw Error('Missing baseline threshold '+candidate.threshold);
  panels.forEach((panel,k)=>{const x=42+(k%3)*440,y=118+row*550+Math.floor(k/3)*255,w=385,h=167,all=[...original.series,...candidate.series],values=all.flatMap(s=>panel.fields.map(f=>f(s))).filter(Number.isFinite);if(!values.length)return;
   const a=Math.min(...values),b=Math.max(...values),margin=Math.max(.02,(b-a)*.08),lo=a-margin,hi=b+margin,t0=Math.min(original.series[0].frame,candidate.series[0].frame),t1=Math.max(original.series.at(-1).frame,candidate.series.at(-1).frame),X=f=>x+(f-t0)/(t1-t0)*w,Y=v=>y+h-(v-lo)/(hi-lo)*h;
   svg+=`<text x="${x}" y="${y-23}" class="title">${candidate.threshold}m/s · ${escape(panel.title)}</text>`;
   for(let j=0;j<5;j++){const yy=y+h*j/4,value=hi-(hi-lo)*j/4;svg+=`<path class="grid" d="M${x} ${yy}H${x+w}"/><text x="${x+3}" y="${yy-3}">${value.toFixed(2)}</text>`;const f=t0+(t1-t0)*j/4;svg+=`<text x="${X(f)-8}" y="${y+h+16}">${Math.round(f)}</text>`;}
   svg+=`<path stroke="#778699" stroke-dasharray="2 5" d="M${X(candidate.analysisStartFrame)} ${y}V${y+h}"/>`;
   panel.fields.forEach((field,c)=>{for(const [data,old]of[[original,true],[candidate,false]]){let open=false,d='';for(const sample of data.series){const value=field(sample);if(!Number.isFinite(value)){open=false;continue;}d+=(open?'L':'M')+X(sample.frame).toFixed(2)+' '+Y(value).toFixed(2)+' ';open=true;}if(d)svg+=`<path class="line" stroke="${colors[c]}" opacity="${old?.55:1}" ${old?'stroke-dasharray="4 4"':''} d="${d}"/>`;}
    svg+=`<text x="${x+c*123}" y="${y+h+34}" style="fill:${colors[c]}">${escape(panel.labels[c])}</text>`;
   });
   if(!original.series.some(s=>panel.fields.some(f=>Number.isFinite(f(s)))))svg+=`<text x="${x}" y="${y+h+49}">Candidate only: baseline did not record this channel.</text>`;
  });
 });
 return svg+`<text x="24" y="${height-14}">X axis: user60Hz frame. Every line uses saved120Hz samples; no support-corner switching is counted as limb motion.</text></svg>`;
}
function main(){const args=process.argv.slice(2),option=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:path.resolve(args[i+1]);},dir=path.join(__dirname,'snapshots'),before=option('--before',path.join(dir,'slide-friction-before-v2.json')),after=option('--after',path.join(dir,'slide-friction-after-v2.json')),out=option('--out',path.join(dir,'slide-friction-stable-points.svg')),a=JSON.parse(fs.readFileSync(before)),b=JSON.parse(fs.readFileSync(after));fs.writeFileSync(out,render(a,b));console.log(JSON.stringify({out,thresholds:b.cases.map(c=>c.threshold),surfaceSha256:b.surfaceSha256}));}
if(require.main===module)main();module.exports={render};
