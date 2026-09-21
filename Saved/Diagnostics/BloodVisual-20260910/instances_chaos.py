import unreal,builtins
s=builtins._blood_visual;w=s['world']
unreal.SystemLibrary.execute_console_command(w,'prophecy.Jolt.BloodInstances.Cleanup')
s['actors']['JoltSetup'].scene_collision.disable_scene_collision()
unreal.SystemLibrary.execute_console_command(w,'prophecy.Jolt.BloodInstances.Setup chaos 0 800 200')
unreal.SystemLibrary.execute_console_command(w,'prophecy.Jolt.BloodInstances.Paint')
unreal.SystemLibrary.execute_console_command(w,'prophecy.Jolt.BloodInstances.Check')
print('CHAOS_INSTANCES_READY')
