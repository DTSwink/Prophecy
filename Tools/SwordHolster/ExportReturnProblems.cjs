// Freeze real release inputs; do not regenerate a different reach/slide.
const fs=require('fs'),path=require('path'),root=path.resolve('Labs/SwordHolsterLab');
const data=require(root+'/data/motions.json'),profile=require(path.resolve('Content/locomotion/SwordHolsterProfile.json')).parameters;
const R=require(root+'/recovery'),H=require(root+'/holster'),setup=require(root+'/data/unreal-setup.json'),holsterMesh=require(root+'/diagnostics/captured-holster-mesh.json');
const existing=require(root+'/diagnostics/problem-motions.json').filter(c=>!c.clip.returnCapture);
const source=JSON.parse(fs.readFileSync('Saved/Diagnostics/Elbow43020261014/release6601135.json','utf8'));
const cases=[['problem_3','Player · sideways hand · UE tick 660','BP_ProphecyManualPoseAgent_C_0',658],['problem_4','Player · sideways hand · UE tick 1135–1138','BP_ProphecyManualPoseAgent_C_0',1137],['problem_5','Agent 1 · fast elbow with IK trial · UE tick 181','BP_ProphecyManualPoseAgent_C_2',177]];
const tr=a=>({p:a.slice(0,3),q:a.slice(3),s:[1,1,1]});
for(const [id,label,actor,release] of cases){
 const rows=source.rows.filter(r=>r.tick>=release-15&&r.tick<=release+48).map(r=>({tick:r.tick,a:r.actors[actor]}));
 if(!rows.some(r=>r.tick===release&&r.a.fields.phase===4))throw Error('Missing release '+label);
 const poses=(a,key)=>data.names.map(n=>tr(n==='root'?(a.authored?.rootFrame||a.root):(a.authored?.[key]||a.visible)[n]));
 const frames=rows.map(({tick,a})=>({tick,pose:poses(a,'bodyPose'),base:poses(a,'base'),holster:tr(a.equipment.holster),insertion:a.fields.insertion,scale:a.fields.scale??1,phase:({1:'Reach',2:'Slide',3:'Holstered',4:'FK return'})[a.fields.phase]||'Held'}));
 const parameters={...profile,...profile.drawBody,sheathe:false,motion:id,startTick:15,duration:(frames.length-1)/60,drawReturn:{...profile.drawReturn,duration:.6},holsterRotationStabilization:.8};
 const grip=frames.find(f=>f.phase==='Slide'&&f.insertion>=.999999);if(!grip)throw Error('Missing fully seated grip '+label);
 const sword=H.compose(H.scaledGrip(setup,grip.scale),grip.pose[data.names.indexOf('hand_r')]),inv=R.qinv(grip.holster.q);
 const seatedSword={p:R.rotate(inv,R.sub(sword.p,grip.holster.p)),q:R.qm(inv,sword.q),s:sword.s};
 const clip={asset:label,fps:60,duration:parameters.duration,loop:false,frames:frames.map(f=>f.base.map(t=>[...t.p,...t.q])),returnCapture:{release:15,firstTick:rows[0].tick,frames,holsterMesh,seatedSword}};
 existing.push({id,label,description:'Exact captured slide and return inputs. FK return controls regenerate the right arm; torso, head and holster use the recording. Reach/body controls do not change this capture.',clip,parameters});
}
fs.writeFileSync(root+'/diagnostics/problem-motions.json',JSON.stringify(existing));console.log('Added three captured return cases; original editable motions retained.');
