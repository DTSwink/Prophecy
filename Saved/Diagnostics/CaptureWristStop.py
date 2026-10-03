import pathlib,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'before'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='wrist_stop_"+mode+"'").replace("s['frame']>=235","s['frame']>=270")
inject="""   sword=a.get_held_sword()
   if sword:
    r['sword']={m.get_name():tr(m.get_world_transform()) for m in sword.get_components_by_class(unreal.StaticMeshComponent)}
    r['grip']=tr(a.get_editor_property('sword_grip_transform'))
"""
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   s['rows'].append(r)\",inject+\"   s['rows'].append(r)\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'CaptureWristStop','exec'))
