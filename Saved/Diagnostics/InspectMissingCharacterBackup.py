import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
path=unreal.Paths.project_saved_dir()+'Autosaves/Game/testNN_Auto6.umap'
package=unreal.load_package(path)
print('BACKUP_PACKAGE',package)
print('SUBSYSTEM_METHODS',[n for n in dir(unreal.EditorActorSubsystem) if any(s in n for s in ['duplicate','copy','paste'])])
print('LOAD_PACKAGE_DOC',unreal.load_package.__doc__)
if package:
    for o in [unreal.find_object(package,n) for n in ['testNN','testNN_Auto6']]:
        if not o:continue
        print('PACKAGE_OBJECT',o.get_path_name(),o.get_class().get_name())
        if isinstance(o,unreal.World):
            for a in unreal.GameplayStatics.get_all_actors_of_class(o,unreal.Actor):
                if 'Prophecy' in a.get_class().get_name():
                    print('BACKUP_ACTOR',a.get_path_name(),a.get_actor_label(),str(a.get_actor_transform()))
print('EDITOR_WORLD_UNCHANGED',ed.get_editor_world().get_path_name())
print('DUPLICATE_DOC',unreal.EditorActorSubsystem.duplicate_actors.__doc__)
