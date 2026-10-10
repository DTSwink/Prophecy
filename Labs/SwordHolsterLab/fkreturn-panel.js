/* Contextual, independently persisted drawing/sheathing return profiles. */
class FKReturnPanel{
 constructor(host,onChange){
  this.host=host;this.onChange=onChange;
  host.innerHTML=`<div class="pinned-actions labelrow"><h2 id="fkReturnTitle">FK return</h2><button id="closeFKReturn" aria-label="Close FK return">×</button></div><div class="sidebar-content"><p class="muted">Starts at slide completion. Independent of reach/slide time curves.</p><label class="check"><input id="fk_enabled" type="checkbox">Enable FK return</label><div id="fkMain"></div><details><summary>Inertia options</summary><label for="fk_springReturn">Method</label><select id="fk_springReturn"><option value="false">Blend + inertia</option><option value="true">Continuous spring</option></select><label for="fk_worldInertia">Inertia space</label><select id="fk_worldInertia"><option value="false">Parent local</option><option value="true">World</option></select><div id="fkAdvanced"></div></details><details><summary>Per-bone inertia</summary><p class="muted">Multiplies main inertia. Left/right share values. Hands inherit motion without local inertia; head aiming stays independently controlled.</p><div id="fkBones"></div></details><p id="fkTiming" class="muted"></p></div>`;
  this.fields=['enabled','springReturn','worldInertia'];
  const field=(id,label,min,max,step)=>`<div class="control"><label for="fk_${id}">${label}</label><input id="fk_${id}" type="number" min="${min}" max="${max}" step="${step}"></div>`;
  for(const [id,label,min,max,step,group] of [
   ['duration','Return time · s',.1,5,.05,'fkMain'],['returnEasing','Easing',0,1,.05,'fkMain'],['inertia','Main inertia',0,1,.05,'fkMain'],
   ['angleTimeSeconds','Extra time per 90° spine turn · s',0,4,.05,'fkAdvanced'],['inertiaHold','Inertia hold',0,.8,.05,'fkAdvanced'],['inertiaDecay','Inertia decay / spring damping',0,4,.05,'fkAdvanced'],['upperArmTwistRemoval','Remove upperarm twist inertia',0,1,.05,'fkAdvanced']
  ]){host.querySelector('#'+group).insertAdjacentHTML('beforeend',field(id,label,min,max,step));this.fields.push(id);}
  for(const key of FKReturn.bones)host.querySelector('#fkBones').insertAdjacentHTML('beforeend',field('bone_'+key,{spine:'Spine',clavicle:'Clavicles',upperarm:'Upper arms',lowerarm:'Forearms',neck_01:'Neck 01',neck_02:'Neck 02',head:'Head'}[key],0,1,.05));
  for(const el of host.querySelectorAll('input,select'))el.addEventListener('change',()=>{
   const profile={...this.profile,boneInertia:{...this.profile.boneInertia}};
   for(const key of this.fields){const e=host.querySelector('#fk_'+key);profile[key]=key==='enabled'?e.checked:['springReturn','worldInertia'].includes(key)?e.value==='true':Number(e.value);}
   for(const key of FKReturn.bones)profile.boneInertia[key]=Number(host.querySelector('#fk_bone_'+key).value);
   this.onChange(FKReturn.sanitize(profile));
  });
 }
 set(action,profile){
  this.profile=profile;this.host.querySelector('#fkReturnTitle').textContent=(action==='draw'?'Drawing':'Sheathing')+' FK return';
  for(const key of this.fields){const e=this.host.querySelector('#fk_'+key);if(key==='enabled')e.checked=profile[key];else e.value=String(profile[key]);}
  for(const key of FKReturn.bones)this.host.querySelector('#fk_bone_'+key).value=profile.boneInertia[key];
  this.host.querySelector('label[for="fk_returnEasing"]').textContent=profile.springReturn?'Pull ramp':'Easing';
  for(const id of ['inertiaHold','upperArmTwistRemoval'])this.host.querySelector('#fk_'+id).parentElement.hidden=profile.springReturn;
 }
 timing(model){this.host.querySelector('#fkTiming').textContent=model.fkReturn?`Return: ${model.fkReturn.timing.duration.toFixed(2)} s · starts at ${model.fkReturn.start.toFixed(2)} s`:'Return inactive or slide not reached.';}
}
