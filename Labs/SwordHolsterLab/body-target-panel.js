/* Two insertion poses for the currently selected D/S action. */
class BodyTargetPanel{
 constructor(host,onEdit,onSelect){
  this.host=host;this.onEdit=onEdit;this.onSelect=onSelect;this.endpoint='clear';
  host.innerHTML=`<div class="pinned-actions labelrow"><h2 id="bodyTargetsTitle">Body poses</h2><button id="closeBodyTargets" aria-label="Close body poses">×</button></div><div class="sidebar-content">
   <label for="pelvisRotationCompensation">Pelvis rotation compensation · <span id="pelvisRotationCompensationValue">1.00</span></label><input id="pelvisRotationCompensation" type="range" min="0" max="1" step="0.01" value="1"><p class="muted">0 follows pelvis rotation · 1 cancels it.</p>
   <label for="bodyEndpoint">Insertion target</label><select id="bodyEndpoint"><option value="clear">0% · blade outside</option><option value="seated">100% · blade seated</option></select>
   <div id="bodyRotations"></div>
   <div class="row-actions"><button id="copyBodyTarget">Copy other target</button><button id="neutralBodyTarget">Neutral target</button></div>
   <div class="control"><label for="maxSpineClavicleAngularSpeed">Max reach angular speed · °/s</label><input id="maxSpineClavicleAngularSpeed" type="number" min="0.01" max="10000" step="5" value="90"></div><p class="muted">Reach arrives with the hand under this limit. Sliding follows insertion; its speed comes from the sliding controls.</p></div>`;
  for(const [bone,label,parent] of [['spine','Spine 05','pelvis'],['right','Right clavicle','spine_05'],['left','Left clavicle','spine_05']]){
   const group=document.createElement('details');group.open=true;group.innerHTML=`<summary>${label}</summary><p class="muted">Relative to ${parent}</p>`;
   for(let axis=0;axis<3;axis++){
    const id=`body_${bone}_${axis}`,row=document.createElement('div');row.className='body-angle';
    row.innerHTML=`<label for="${id}">${'XYZ'[axis]} · °</label><input id="${id}" type="range" min="-180" max="180" step="0.1"><input id="${id}_number" aria-label="${label} ${'XYZ'[axis]} degrees" type="number" min="-180" max="180" step="0.1">`;
    const [range,number]=row.querySelectorAll('input');
    const edit=(el,commit)=>{range.value=number.value=el.value;this.profile[this.endpoint][bone][axis]=Number(el.value);this.onEdit(BodyReach.sanitize(this.profile),commit);};
    range.addEventListener('input',()=>edit(range,false));range.addEventListener('change',()=>edit(range,true));number.addEventListener('change',()=>edit(number,true));group.append(row);
   }
   host.querySelector('#bodyRotations').append(group);
  }
  const pole=document.createElement('details');pole.open=true;pole.innerHTML=`<summary>Right elbow direction</summary><p class="muted">Angle in the moving arm frame. 0° = down; ±90° = either side; ±180° = up. Saved for this action at this insertion target.</p><div class="body-angle"><label for="body_pole">°</label><input id="body_pole" type="range" min="-180" max="180" step="0.1"><input id="body_pole_number" aria-label="Elbow pole angle degrees" type="number" min="-180" max="180" step="0.1"></div><label><input id="swordRelativeSlidePole" type="checkbox"> Sword-relative pole while sliding</label><p class="muted">Carries the entry reference with the sword during sliding. Reach is unchanged.</p><label for="maxElbowPoleAngularSpeed">Max pole speed · °/s</label><input id="maxElbowPoleAngularSpeed" type="number" min="0" max="10000" step="10" value="180"><p class="muted">Upper speed limit. During reach, slows down to arrive with the hand; if capped, keeps catching up during sliding. Arm sweeps and torso turns do not consume this speed. 0 holds the starting preference.</p>`;
  host.querySelector('#bodyRotations').append(pole);
  const range=pole.querySelector('#body_pole'),number=pole.querySelector('#body_pole_number');
  const editPole=(el,commit)=>{range.value=number.value=el.value;this.profile[this.endpoint].pole=Number(el.value);this.onEdit(BodyReach.sanitize(this.profile),commit);};
  range.oninput=()=>editPole(range,false);range.onchange=()=>editPole(range,true);number.onchange=()=>editPole(number,true);
  host.querySelector('#bodyEndpoint').onchange=e=>{this.endpoint=e.target.value;this.set(this.profile);this.onSelect(this.endpoint);};
  host.querySelector('#copyBodyTarget').onclick=()=>{this.profile[this.endpoint]=structuredClone(this.profile[this.endpoint==='clear'?'seated':'clear']);this.set(this.profile);this.onEdit(this.profile,true);};
  host.querySelector('#neutralBodyTarget').onclick=()=>{this.profile[this.endpoint]={spine:[0,0,0],right:[0,0,0],left:[0,0,0]};this.set(this.profile);this.onEdit(this.profile,true);};
 }
 set(profile){this.profile=BodyReach.sanitize(profile);this.host.querySelector('#body_pole').value=this.host.querySelector('#body_pole_number').value=this.profile[this.endpoint].pole;this.host.querySelector('#bodyEndpoint').value=this.endpoint;for(const bone of ['spine','right','left'])for(let k=0;k<3;k++){const id=`#body_${bone}_${k}`,v=this.profile[this.endpoint][bone][k];this.host.querySelector(id).value=v;this.host.querySelector(id+'_number').value=v;}}
}
