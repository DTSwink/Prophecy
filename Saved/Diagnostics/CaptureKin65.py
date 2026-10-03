import unreal,pathlib,sys
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
root=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
tag=sys.argv[1] if len(sys.argv)>1 else 'kin65'
src=(root/'CaptureKnee202.py').read_text().replace('clock>=175','clock>=999999').replace("s['frame']>=280","s['frame']>=95")
src=src.replace("   s['rows'].append(r)","   r['actor_transform']=tr(a.get_actor_transform())\n   r['components']={m.get_name():dict(world=tr(m.get_world_transform()),relative=tr(m.get_relative_transform()),anim=str(m.get_anim_instance()),sim=m.is_any_simulating_physics()) for m in a.get_components_by_class(unreal.SkeletalMeshComponent)}\n   s['rows'].append(r)")
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
extra="""   cube=a.get_editor_property('magic Cube')
   lib=unreal.ProphecyRootPhysicsLibrary
   r['magic']=str(lib.get_root_magic_velocity(a))
   r['cube']=dict(transform=tr(cube.get_world_transform()),velocity=str(cube.get_physics_linear_velocity())) if cube else None
"""
if tag=='kin65_no_magic':extra+="   if clock>=40:lib.set_root_magic_velocity(a,unreal.Vector(0,0,0),False)\n"
src=src.replace("   s['rows'].append(r)",extra+"   s['rows'].append(r)")
exec(compile(src,'CaptureKin65','exec'))
