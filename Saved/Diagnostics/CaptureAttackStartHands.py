import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
root=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
mode=sys.argv[1] if len(sys.argv)>1 else 'disabled'
wrapper=(root/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='entry_hands_"+mode+"'").replace('clock>=140','clock>=999999').replace("s['frame']>=235","s['frame']>="+('240' if mode in ('default','handoff') else '210'))
inject=""
if mode!='disabled':
 ref={'pelvis':0.,'mixed':.5,'spine':1.,'zero':.5,'default':.5,'handoff':.5}[mode]
 alpha=0. if mode=='zero' else 1.
 timing='.1,.3' if mode in ('default','handoff') else '.35,.35'
 inject="   if clock==1:print('ENTRY_HANDS_CONFIG',unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary')).call_method('SetAttackStartHandInertia',(a,True,"+timing+","+repr(ref)+",.25,1.,"+repr(alpha)+",True,True)))\n"
if mode=='handoff':inject+="   if clock==155:print('ENTRY_HALF',a.set_nn_half_attack_enabled(True))\n   if clock==161:print('ENTRY_FULL',a.set_nn_half_attack_enabled(False))\n"
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   s['rows'].append(r)\",inject+\"   s['rows'].append(r)\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'EntryHands','exec'))
