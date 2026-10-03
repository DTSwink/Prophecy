import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
 print('DRIVE {} mode={} mult={} settings={}'.format(a.get_name(),a.get_simulation_mode(),a.get_editor_property('physical_drive_strength_multiplier'),a.get_editor_property('physical_drive_settings')))
