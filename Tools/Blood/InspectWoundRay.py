"""Read-only live wound emitter and attachment inspection; never controls Play."""
import json, pathlib, unreal

out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/WoundRay'
out.mkdir(parents=True, exist_ok=True)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = [a for a in registry.get_assets_by_class(unreal.TopLevelAssetPath('/Script/Niagara', 'NiagaraSystem')) if 'bloodwound' in str(a.asset_name).lower()]
def dump(obj, name):
    t = unreal.AssetExportTask()
    t.object = obj
    t.filename = str(out / (name + '.txt'))
    t.exporter = unreal.ObjectExporterT3D()
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    return unreal.Exporter.run_asset_export_task(t)
result = {'play': bool(ed.get_game_world()), 'assets': [], 'components': []}
result['swords'] = []
for a in assets:
    obj = a.get_asset()
    result['assets'].append({'path': obj.get_path_name(), 'export': dump(obj, obj.get_name())})
for world in [ed.get_editor_world(), ed.get_game_world()]:
    if not world: continue
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        if actor.get_class().get_name() == 'A_Sword_C':
            sword = {'actor': actor.get_path_name()}
            for prop in ['blade length', 'sword']:
                try: sword[prop] = str(actor.get_editor_property(prop))
                except Exception: pass
            sword['meshes'] = [{'name': c.get_name(), 'transform': str(c.get_world_transform()), 'bounds': str(c.get_local_bounds())} for c in actor.get_components_by_class(unreal.StaticMeshComponent)]
            result['swords'].append(sword)
        for c in actor.get_components_by_class(unreal.NiagaraComponent):
            asset = c.get_asset()
            if not asset or 'bloodwound' not in asset.get_name().lower(): continue
            parent = c.get_attach_parent()
            row = {'component': c.get_path_name(), 'asset': asset.get_path_name(), 'transform': str(c.get_world_transform()), 'parent': str(parent), 'socket': str(c.get_attach_socket_name()), 'active': c.is_active()}
            if parent: row['parent_transform'] = str(parent.get_world_transform())
            result['components'].append(row)
            dump(c, 'component_' + str(len(result['components'])))
(out / 'state.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
