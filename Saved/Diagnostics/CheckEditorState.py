import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(ed.get_game_world()))
print('DirtyMaps',[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
print('DirtyContent',[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('LeftoverFixtures',[a.get_name() for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.actor_has_tag('CodexConstraintFixture')])
