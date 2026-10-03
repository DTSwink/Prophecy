import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
w=ed.get_editor_world();root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootDistanceSmoothing-20261002'
def scene():
 return {a.get_name():str(a.get_actor_transform()) for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
before=scene()
for command in ('Prophecy.Editor.RepairLibraryDefaults','Prophecy.Editor.LiveAgentTypes Inspect','Prophecy.Sword.AuditCollisionGraph'):
 unreal.SystemLibrary.execute_console_command(w,command)
assert scene()==before,'Scene changed'
for source,target in [('SwordThigh/BlueprintGraph.txt','graph-after.txt'),('LiveLibraryDefaults.txt','library-defaults.txt'),('LiveAgentTypes-Inspect.txt','native-types.txt')]:
 (root/target).write_bytes((root.parent/source).read_bytes())
(root/'final-scene.json').write_text(json.dumps(dict(actors_unchanged=len(before),play_active=False,map=w.get_path_name()),indent=2),encoding='utf8')
print('ROOT_SMOOTHING_FINAL',len(before),(root/'library-defaults.txt').read_text(encoding='utf-8-sig'),(root/'native-types.txt').read_text(encoding='utf-8-sig'))
