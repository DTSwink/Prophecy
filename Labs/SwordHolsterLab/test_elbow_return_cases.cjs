const assert=require('node:assert/strict'),H=require('./holster'),P=require('./sequence'),R=require('./recovery'),F=require('./fkreturn');
const original=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),cases=require('./diagnostics/problem-motions.json').filter(c=>!c.clip.returnCapture);
const data={...original,motions:{...original.motions}};for(const c of cases)data.motions[c.id]=c.clip;
const d=(a,b)=>R.length(R.sub(a,b));let count=0,maxSeamStep=0;
for(const c of cases)for(const noCheat of [true,false])for(const sheathe of [false,true]){
 const key=sheathe?'sheatheReturn':'drawReturn',o={...c.parameters,...c.parameters[sheathe?'sheatheBody':'drawBody'],noCheat,sheathe,duration:5,[key]:c.parameters[key]},m=P.prepare(data,setup,o),ret=m.armReturn||m.fkReturn;
 assert(m.completionTick!==null);assert(ret);
 for(const f of m.frames){assert(f.pose.every(t=>[...t.p,...t.q].every(Number.isFinite)));for(const j of m.arm)assert(Math.abs(R.length(f.pose[j].q)-1)<1e-8);}
 const times=[.1,.25,.35,.6,.99].map(x=>ret.start+x*ret.timing.duration),expected=times.map(t=>H.sampleBody(m,t));
 for(let i=times.length-1;i>=0;i--){H.sampleBody(m,ret.start);assert.deepEqual(H.sampleBody(m,times[i]),expected[i]);}
 const a=H.sampleBody(m,m.completionTick/60).pose,base=H.motion(data,o.motion,m.completionTick/60,o.gazeYaw);
 for(const j of m.arm)assert(d(a[j].p,base[j].p)<1e-7);
 if(c.id==='problem_2'&&noCheat&&!sheathe){const a=m.frames[71].pose,b=m.frames[72].pose,step=d(a[m.arm[1]].p,b[m.arm[1]].p);maxSeamStep=Math.max(maxSeamStep,step);assert(step<6);assert(H.angle(a[m.arm[1]].q,b[m.arm[1]].q)<15);}
 count++;
}
console.log(JSON.stringify({passed:true,count,maxSeamStep}));
