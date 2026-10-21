"""Verify reflection and run an isolated native fixture; never starts editor Play."""
import json,pathlib,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play left untouched'
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyPhysicsConstraintBlueprintLibrary:SetPikeWoundCorrection')
assert fn,'Per-constraint native node missing'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeWoundNode'
out.mkdir(parents=True,exist_ok=True)
if '--tests' in sys.argv:
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Constraints.PikeWoundCorrection')
    print('Isolated native pike fixture requested; editor Play not started')
elif '--save' in sys.argv:
    bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    print('Saved only A_Sword')
else:
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
    info=dict(display_name=unreal.EditorAssetLibrary.get_metadata_tag(fn,'DisplayName'),play=False,
              python_preview_active=('pike_wound_demo' in globals() and pike_wound_demo.handle is not None),
              dirty=[x.get_path_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
                     +list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])
    (out/'live.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info))
