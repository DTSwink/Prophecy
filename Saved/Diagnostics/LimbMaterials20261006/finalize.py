import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbMaterials20261006'
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
ss=unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
sections=[ss.get_num_sections(mesh,i) for i in range(ss.get_lod_count(mesh))]
assert sections==[1,1,1],sections
paths=['/Game/_mygame/SKM_UEFN_Mannequin','/Game/_mygame/Materials/LimbColors/T_LimbPalette','/Game/_mygame/Materials/LimbColors/M_UEFN_LimbColors','/Game/_mygame/Materials/LimbColors/M_UEFN_Bicolor_LimbColors']
for path in paths:assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True),path
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
result={'sections_per_lod':sections,'saved_assets':paths,'blueprint':r}
(p/'verified.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
