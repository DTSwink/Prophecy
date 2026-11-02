import os,json,pathlib,unreal
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
paths=unreal.EditorAssetLibrary.list_assets('/Game/_mygame/spear',recursive=True,include_folder=False)
mesh=unreal.load_asset('/Game/_mygame/spear/SM_ImperialSpear')
b=mesh.get_bounding_box()
report={'bounds_min':[b.min.x,b.min.y,b.min.z],'bounds_max':[b.max.x,b.max.y,b.max.z],'assets':list(paths)}
for p in paths:
 assert unreal.EditorAssetLibrary.save_asset(p,only_if_is_dirty=False)
(out/'import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
