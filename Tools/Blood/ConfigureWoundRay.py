"""Install the scoped wound-ray/paint callback fix; leave unrelated assets alone."""
import unreal, pathlib, shutil, json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play preserved'
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/WoundRay'
out.mkdir(parents=True,exist_ok=True)
for name,folder in [('NS_bloodwound','blood2'),('A_DecalManager','blood2')]:
    source=root/'Content/_mygame'/folder/(name+'.uasset')
    target=out/(name+'.before.uasset')
    if not target.exists():shutil.copy2(source,target)
for source,name in [('/Niagara/Modules/Collision/CollisionQueryAndResponse','WoundQuerySync'),('/Niagara/Modules/Collision/Collision','WoundCollisionSync')]:
    destination='/Game/Prophecy/BloodTexturePainting/Modules/'+name
    if not unreal.EditorAssetLibrary.does_asset_exist(destination):
        assert unreal.EditorAssetLibrary.duplicate_asset(source,destination)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Blood.WireExperiment')
print('Wound setup invoked; verify native log, graph and emitter stores before saving.')
