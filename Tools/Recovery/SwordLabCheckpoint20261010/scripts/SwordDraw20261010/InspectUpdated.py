import unreal,pathlib,json,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-updated-before.txt')
print('PLAY',bool(ed.get_game_world()))
print('DIRTY',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
a=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)[0]
c=next(c for c in a.get_components_by_class(unreal.ChildActorComponent) if c.get_name().startswith('SwordRef'))
s=c.get_editor_property('child_actor')
for x in s.get_components_by_class(unreal.SceneComponent):
 print(x.get_name(),'parent',x.get_attach_parent(),'relative',x.get_relative_transform(),'world',x.get_world_transform())
 if isinstance(x,unreal.StaticMeshComponent):print('BOUNDS',x.get_local_bounds())
print('GRIP',a.get_editor_property('sword_grip_transform'))
