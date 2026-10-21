"""Status/build/isolated tests for coupled pike. Does not alter assets or control Play."""
import hashlib,json,pathlib,shutil,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print(json.dumps(dict(play=bool(ed.get_game_world()),map=ed.get_editor_world().get_path_name(),
 dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])))
if '--close' in sys.argv:
    assert not ed.get_game_world(),'User Play preserved'
    root=pathlib.Path(unreal.Paths.project_dir())
    out=root/'Saved/Diagnostics/CoupledPike';out.mkdir(parents=True,exist_ok=True)
    dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    for package in dirty:
        name=package.get_path_name()
        assert name.startswith('/Game/'),name
        base=root/'Content'/name[6:]
        for suffix in ('.uasset','.umap'):
            source=base.with_suffix(suffix)
            if source.exists():shutil.copy2(source,out/(source.name+'.before-save'))
    if dirty:assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty,False)
    assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    paths=[root/'Content/_mygame/sword/A_Sword.uasset',root/'Content/explosionVFX.umap']
    receipt=dict(saved=[p.get_path_name() for p in dirty],map=ed.get_editor_world().get_path_name(),hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (out/'restart-preservation.json').write_text(json.dumps(receipt,indent=2))
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'CLOSE_SLATE_MAINFRAME')
elif '--verify' in sys.argv:
    root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/CoupledPike'
    receipt=json.loads((out/'restart-preservation.json').read_text())
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in receipt['hashes'].items()),'Saved assets changed'
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyPhysicsConstraintBlueprintLibrary:SetPikeWoundCorrection')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    report=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report,report
    print('Saved map/sword hashes unchanged; native node and Blueprint reflection verified')
elif '--build' in sys.argv or '--test' in sys.argv:
    assert not ed.get_game_world(),'Active Play preserved; wait for user to stop before patching'
    command='LiveCoding.Compile' if '--build' in sys.argv else 'Automation RunTests Prophecy.Jolt.Constraints.PikeWoundCorrection'
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
    print(command)
