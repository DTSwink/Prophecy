"""Isolated Unreal import/IK retarget/FBX export for the two October 24 throws."""
import json
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
AUDIT = ROOT / 'Saved/Diagnostics/MixamoThrows20261024'
OUT = Path('C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024')
PACKAGE = '/Game/_mygame/animations/MixamoThrows20261024'
AUDIT.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
report = {'exports': [], 'package': PACKAGE}

def save_report():
    (AUDIT / 'unreal-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

def create(name, cls, factory):
    path = PACKAGE + '/' + name
    existing = u.load_asset(path)
    return existing or u.AssetToolsHelpers.get_asset_tools().create_asset(name, PACKAGE, cls, factory)

def main():
    target = u.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin')
    assert target
    report['target_mesh'] = target.get_path_name()
    report['target_skeleton'] = target.skeleton.get_path_name()
    imports = []
    source_mesh = u.load_asset(PACKAGE + '/Source/Throwing/Throwing')
    if source_mesh and not source_mesh.skeleton:
        source_mesh = None
    for filename, name in [('Throwing.fbx', 'Throwing'), ('Throw Object.fbx', 'Throw_Object')]:
        folder = PACKAGE + '/Source/' + name
        existing = u.EditorAssetLibrary.list_assets(folder, recursive=True, include_folder=False)
        assets = [u.load_asset(p) for p in existing]
        if not any(isinstance(a, u.AnimSequence) for a in assets):
            options = u.FbxImportUI()
            options.automated_import_should_detect_type = False
            options.import_mesh = source_mesh is None
            options.import_as_skeletal = True
            options.import_animations = True
            options.import_materials = False
            options.import_textures = False
            options.create_physics_asset = False
            options.mesh_type_to_import = (u.FBXImportType.FBXIT_SKELETAL_MESH if source_mesh is None else u.FBXImportType.FBXIT_ANIMATION)
            if source_mesh:
                options.skeleton = source_mesh.skeleton
            options.anim_sequence_import_data.set_editor_property('animation_length', u.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
            options.anim_sequence_import_data.set_editor_property('use_default_sample_rate', False)
            options.anim_sequence_import_data.set_editor_property('custom_sample_rate', 30)
            options.anim_sequence_import_data.set_editor_property('snap_to_closest_frame_boundary', True)
            options.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose', False)
            options.skeletal_mesh_import_data.set_editor_property('use_t0_as_ref_pose', False)
            task = u.AssetImportTask()
            task.filename = str(AUDIT / 'PreparedSources' / filename)
            task.destination_path = folder
            task.destination_name = name + '_Anim' if source_mesh else name
            task.automated = True
            task.replace_existing = True  # Only this task's dedicated import packages.
            task.save = True
            task.options = options
            task.factory = u.FbxFactory()
            u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            assets = [u.load_asset(p) for p in u.EditorAssetLibrary.list_assets(folder, recursive=True, include_folder=False)]
            for imported in assets:
                assert u.EditorAssetLibrary.save_loaded_asset(imported, only_if_is_dirty=False)
        if source_mesh is None:
            source_mesh = next(a for a in assets if isinstance(a, u.SkeletalMesh))
        anim = next(a for a in assets if isinstance(a, u.AnimSequence))
        imports.append((filename, name, anim))
    report['source_mesh'] = source_mesh.get_path_name()
    report['imports'] = [{'file': f, 'asset': a.get_path_name(), 'seconds': a.get_play_length()} for f, n, a in imports]
    save_report()

    rigs = []
    for name, mesh in [('IK_MixamoThrows', source_mesh), ('IK_UEFNThrows', target)]:
        existed = u.EditorAssetLibrary.does_asset_exist(PACKAGE + '/' + name)
        rig = create(name, u.IKRigDefinition, u.IKRigDefinitionFactory())
        ctrl = u.IKRigController.get_controller(rig)
        if not existed:
            assert ctrl.set_skeletal_mesh(mesh)
            assert ctrl.apply_auto_generated_retarget_definition(), name
            if mesh == target:
                assert ctrl.apply_auto_fbik()
        rigs.append(rig)
        report[name] = [{'name': str(c.chain_name), 'start': str(ctrl.get_retarget_chain_start_bone(c.chain_name)), 'end': str(ctrl.get_retarget_chain_end_bone(c.chain_name))} for c in ctrl.get_retarget_chains()]
    retargeter_existed = u.EditorAssetLibrary.does_asset_exist(PACKAGE + '/RTG_MixamoThrows_to_UEFN')
    rtg = create('RTG_MixamoThrows_to_UEFN', u.IKRetargeter, u.IKRetargetFactory())
    rc = u.IKRetargeterController.get_controller(rtg)
    rc.set_ik_rig(u.RetargetSourceOrTarget.SOURCE, rigs[0])
    rc.set_ik_rig(u.RetargetSourceOrTarget.TARGET, rigs[1])
    rc.set_preview_mesh(u.RetargetSourceOrTarget.SOURCE, source_mesh)
    rc.set_preview_mesh(u.RetargetSourceOrTarget.TARGET, target)
    if not retargeter_existed:
        rc.add_default_ops()
        rc.auto_map_chains(u.AutoMapChainType.EXACT, True)
        rc.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET)
    report['chain_mapping'] = {c['name']: str(rc.get_source_chain(c['name'])) for c in report['IK_UEFNThrows']}
    for asset in [*rigs, rtg]:
        assert u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    save_report()

    for filename, name, source_anim in imports:
        dest = PACKAGE + '/UEFN_' + name
        anim = u.load_asset(dest)
        if not anim:
            data = u.get_editor_subsystem(u.EditorAssetSubsystem).find_asset_data(source_anim.get_path_name())
            results = u.IKRetargetBatchOperation.duplicate_and_retarget([data], source_mesh, target, rtg,
                prefix='UEFN_', suffix='', include_referenced_assets=False, overwrite_existing_files=False)
            assert len(results) == 1, results
            anim = results[0].get_asset()
            assert u.EditorAssetLibrary.rename_asset(anim.get_path_name(), dest)
            anim = u.load_asset(dest)
        assert anim.get_editor_property('skeleton') == target.skeleton
        anim.set_preview_skeletal_mesh(target)
        assert abs(anim.get_play_length() - source_anim.get_play_length()) < 1e-5
        assert u.EditorAssetLibrary.save_loaded_asset(anim, only_if_is_dirty=False)
        path = OUT / ('UEFN_' + name + '_AnimationOnly.fbx')
        options = u.FbxExportOption()
        options.ascii = False
        options.collision = False
        options.level_of_detail = False
        options.export_morph_targets = False
        options.export_preview_mesh = False
        options.force_front_x_axis = False
        options.map_skeletal_motion_to_root = False
        options.export_local_time = True
        task = u.AssetExportTask()
        task.object = anim
        task.filename = str(path)
        task.automated = True
        task.prompt = False
        task.replace_identical = True
        task.options = options
        assert u.Exporter.run_asset_export_task(task), list(task.errors)
        assert path.stat().st_size > 1000
        report['exports'].append({'source': filename, 'asset': anim.get_path_name(), 'file': str(path), 'seconds': anim.get_play_length(), 'bytes': path.stat().st_size})
        save_report()
    report['success'] = True
    save_report()

try:
    main()
except Exception:
    report['error'] = traceback.format_exc()
    save_report()
    u.log_error(report['error'])
finally:
    u.SystemLibrary.quit_editor()
