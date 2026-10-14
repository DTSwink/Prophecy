/* Contextual, independently persisted drawing/sheathing return profiles. */
class FKReturnPanel{
 constructor(host,onChange){
  this.host=host;this.onChange=onChange;
  host.innerHTML=`<div class="pinned-actions labelrow"><h2 id="fkReturnTitle">FK return</h2><button id="closeFKReturn" aria-label="Close FK return">×</button></div><div class="sidebar-content"><p id="fkStartHelp" class="muted"></p><label class="check"><input id="fk_enabled" type="checkbox">Enable FK return</label><div id="fkMain"></div><details><summary>Inertia options</summary><label for="fk_springReturn">Method</label><select id="fk_springReturn"><option value="false">Blend + inertia</option><option value="true">Continuous spring</option></select><label for="fk_worldInertia">Inertia space</label><select id="fk_worldInertia"><option value="false">Parent local</option><option value="true">World</option></select><div id="fkAdvanced"></div></details><details><summary>Per-bone inertia</summary><p class="muted">Multiplies main inertia. Left/right share values. Drawing’s right hand preserves incoming rotation and local position motion at release, with bone lengths retained. Head aiming stays independently controlled.</p><div id="fkBones"></div></details><p id="fkTiming" class="muted"></p></div>`;
  this.fields=['enabled','springReturn','worldInertia'];
  const curveHost=document.createElement('div');curveHost.id='fkReturnCurveEditor';host.querySelector('#fkMain').after(curveHost);
  this.curve=new RetimeEditor(curveHost,'Return timing',points=>this.onChange(FKReturn.sanitize({...this.profile,timingCurve:points})));
  curveHost.insertAdjacentHTML('afterend','<p class="muted">Shapes return progress without changing its duration. Applies to body return and, after release, arm return. Head and base animation keep their own clocks.</p>');
  const field=(id,label,min,max,step)=>`<div class="control"><label for="fk_${id}">${label}</label><input id="fk_${id}" type="number" min="${min}" max="${max}" step="${step}"></div>`;
  for(const [id,label,min,max,step,group] of [
   ['startFraction','Start at insertion fraction',0,1,.01,'fkMain'],['duration','Return time · s',.1,5,.05,'fkMain'],['returnEasing','Easing',0,1,.05,'fkMain'],['inertia','Main inertia',0,1,.05,'fkMain'],
   ['angleTimeSeconds','Extra time per 90° spine turn · s',0,4,.05,'fkAdvanced'],['inertiaHold','Inertia hold',0,.8,.05,'fkAdvanced'],['inertiaDecay','Inertia decay / spring damping',0,4,.05,'fkAdvanced'],['upperArmTwistRemoval','Remove upperarm twist inertia',0,1,.05,'fkAdvanced']
  ]){host.querySelector('#'+group).insertAdjacentHTML('beforeend',field(id,label,min,max,step));this.fields.push(id);}
  host.querySelector('#fkMain').insertAdjacentHTML('beforeend','<div id="fkArmIK"><label class="check"><input id="fk_armIKEnabled" type="checkbox">Blend right arm FK &rarr; IK</label><div class="pair">'+field('armIKStart','Start &middot; return fraction',0,1,.01)+field('armIKEnd','End &middot; return fraction',0,1,.01)+'</div><p class="muted" id="fkArmIKHelp"></p><p class="muted" id="fkArmIKTiming"></p></div>');
  this.fields.push('armIKEnabled','armIKStart','armIKEnd');
  host.querySelector('#fkMain').insertAdjacentHTML('beforeend','<div class="control" id="fkHandRotationControl"><label for="fk_handRotationFKAlpha">Hand rotation · FK alpha <span id="fkHandRotationValue">1.00</span></label><input id="fk_handRotationFKAlpha" type="range" min="0" max="1" step="0.01"><p class="muted">0 = independent root-local rotation · 1 = current FK. Starts after drawing clears the holster; hand position still follows the arm.</p></div>');
  host.querySelector('#fkMain').insertAdjacentHTML('beforeend','<div id="fkSwordPoint"><h3>Draw &middot; hand-axis turn</h3>'+field('swordPointSpeed','Angular speed &middot; &deg;/s',-3600,3600,10)+field('swordPointExponent','Sigmoid exponent',1,8,.1)+field('swordPointCutoff','Cutoff &middot; return fraction',0,.99,.01)+'<p class="muted">0 speed = off. Starts at D0%. Rotate around hand local X; negative speed reverses the sweep. No target direction or angle stop. 1 exponent = constant speed; higher eases both ends with this speed as the peak. Cutoff .5 uses the first half of the arm return, then continues the existing return from the reached rotation. Independent of timing curves.</p></div>');
  this.fields.push('swordPointSpeed','swordPointExponent','swordPointCutoff');
  this.fields.push('handRotationFKAlpha');
  host.querySelector('#fk_handRotationFKAlpha').addEventListener('input',e=>{host.querySelector('#fkHandRotationValue').textContent=Number(e.target.value).toFixed(2);});
  for(const key of FKReturn.bones)host.querySelector('#fkBones').insertAdjacentHTML('beforeend',field('bone_'+key,{spine:'Spine',clavicle:'Clavicles',upperarm:'Upper arms',lowerarm:'Forearms',hand:'Right hand · draw release',neck_01:'Neck 01',neck_02:'Neck 02',head:'Head'}[key],0,1,.05));
  for(const el of host.querySelectorAll('input,select'))el.addEventListener('change',()=>{
   const profile={...this.profile,boneInertia:{...this.profile.boneInertia}};
   for(const key of this.fields){const e=host.querySelector('#fk_'+key);profile[key]=['enabled','armIKEnabled'].includes(key)?e.checked:['springReturn','worldInertia'].includes(key)?e.value==='true':Number(e.value);}
   if(this.action==='draw')profile.startFraction=1-profile.startFraction;
   for(const key of FKReturn.bones)profile.boneInertia[key]=Number(host.querySelector('#fk_bone_'+key).value);
   this.onChange(FKReturn.sanitize(profile));
  });
 }
 set(action,profile){
  this.action=action;this.profile=profile;this.host.querySelector('#fkReturnTitle').textContent=(action==='draw'?'Drawing':'Sheathing')+' FK return';
  this.curve.set(profile.timingCurve);
  this.host.querySelector('#fkHandRotationControl').hidden=action!=='draw';
  this.host.querySelector('#fkSwordPoint').hidden=action!=='draw';
  this.host.querySelector('#fkHandRotationValue').textContent=profile.handRotationFKAlpha.toFixed(2);
  for(const key of this.fields){const e=this.host.querySelector('#fk_'+key);if(['enabled','armIKEnabled'].includes(key))e.checked=profile[key];else e.value=String(key==='startFraction'&&action==='draw'?Number((1-profile[key]).toFixed(12)):profile[key]);}
  this.host.querySelector('#fkArmIKHelp').textContent='After release only. 0 = release, 1 = arm return complete. At Start, capture the current hand position. Blend from FK into its direct root-local path toward the current animation by End. Wrist rotation stays separate; IK respects arm length. Uncheck for original FK.';
  this.host.querySelector('#fkStartHelp').textContent=action==='draw'?'Drawing: insertion falls from 1 to 0. Body return starts at this value; the gripping arm follows the sword until 0.':'Sheathing: insertion rises from 0 to 1. Body return starts at this value; the gripping arm follows the sword until 1.';
  for(const key of FKReturn.bones)this.host.querySelector('#fk_bone_'+key).value=profile.boneInertia[key];
  this.host.querySelector('#fk_bone_hand').parentElement.hidden=action!=='draw';
  this.host.querySelector('label[for="fk_returnEasing"]').textContent=profile.springReturn?'Pull ramp':'Easing';
  for(const id of ['inertiaHold','upperArmTwistRemoval'])this.host.querySelector('#fk_'+id).parentElement.hidden=profile.springReturn;
 }
 timing(model,offset=0){const ret=model?.armReturn||model?.fkReturn;this.host.querySelector('#fkArmIKTiming').textContent=ret?'Blend duration: '+((this.profile.armIKEnd-this.profile.armIKStart)*ret.timing.duration).toFixed(3)+' s.':'';this.host.querySelector('#fkTiming').textContent=model?.fkReturn?`Body starts ${(offset+model.fkReturn.start).toFixed(2)} s · arm starts ${(offset+(model.armReturn?.start??model.fkReturn.start)).toFixed(2)} s. Return ${model.fkReturn.timing.duration.toFixed(2)} s${model.fkReturn.gripDelay>1e-4?' · body waits at arm reach limit':''}.`:'Return inactive or slide not reached.';}
}
