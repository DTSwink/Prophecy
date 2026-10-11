"""Read-only editor snapshot before the authorized overnight investigation."""
import unreal, pathlib, json, hashlib, shutil
root = pathlib.Path(unreal.Paths.project_dir())
out = root / 'Saved/Diagnostics/SwordOvernight20261011'
out.mkdir(parents=True, exist_ok=True)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')
assets = {}
for name in ['Content/testNN.umap', 'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset', 'Content/_mygame/sword/A_Sword.uasset', 'Content/locomotion/SwordHolsterProfile.json']:
    data = (root / name).read_bytes()
    target = out / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists(): target.write_bytes(data)
    assets[name] = hashlib.sha256(data).hexdigest()
graph = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
if graph.exists() and not (out / 'before-graph.txt').exists(): shutil.copy2(graph, out / 'before-graph.txt')
result = dict(map=world.get_path_name(), play=ed.get_game_world() is not None, assets=assets,
    dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())])
(out / 'editor-before.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(result)
