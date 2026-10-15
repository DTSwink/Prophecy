"""Create only separate animation previews. No level actors, PHAT or mesh edits."""
import json,hashlib,sys
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/MimicKitTransfer/no-armature-3913'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None,'Do not interfere with Play'
def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
before=dirty()
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
skeleton=mesh.get_editor_property('skeleton')
assets=[]
tags=sys.argv[1:] or ['Newton','Jolt']
for tag in tags:
    data=json.loads((out/f'skin_{tag}.json').read_text())
    assert not unreal.EditorAssetLibrary.does_asset_exist(data['asset']), 'Preview exists; refuse to overwrite'
    factory=unreal.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton',skeleton)
    factory.set_editor_property('preview_skeletal_mesh',mesh)
    folder,name=data['asset'].rsplit('/',1)
    seq=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,unreal.AnimSequence,factory)
    assert seq
    ctl=seq.get_editor_property('controller')
    ctl.open_bracket('Import reduced-rig recorded physics',False)
    try:
        ctl.set_frame_rate(unreal.FrameRate(data['fps'],1),False)
        ctl.set_number_of_frames(unreal.FrameNumber(data['frames']-1),False)
        for track in data['tracks']:
            ctl.add_bone_curve(track['name'],False)
            assert ctl.set_bone_track_keys(track['name'],[unreal.Vector(*p) for p in track['positions']],
                [unreal.Quat(*q) for q in track['rotations']],[unreal.Vector(1,1,1)]*data['frames'],False)
    finally:ctl.close_bracket(False)
    seq.set_editor_property('enable_root_motion',False)
    seq.set_editor_property('force_root_lock',False)
    for k,v in dict(Source=data['source'],SourceSHA256=data['source_sha256'],Purpose=data['title'],
                    Skinning='Existing original mesh and weights; 15 physical anchors, other bones retain bind locals',
                    Warning='Recorded physics preview, not a live policy controller').items():
        unreal.EditorAssetLibrary.set_metadata_tag(seq,k,v)
    assert unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=True)
    assets.append(seq)
after=dirty()
receipt=dict(assets=[s.get_path_name() for s in assets],mesh=mesh.get_path_name(),dirty_before=before,dirty_after=after,
             animation_library_methods=[x for x in dir(unreal.AnimationLibrary) if 'bone' in x.lower()] if hasattr(unreal,'AnimationLibrary') else [],
             controller_methods=[x for x in dir(ctl) if any(s in x for s in ['model','track','bone'])])
(out/('skin-import-'+'-'.join(tags)+'-receipt.json' if sys.argv[1:] else 'skin-import-receipt.json')).write_text(json.dumps(receipt,indent=2))
assert before==after, 'Unexpected package dirtiness; do not save unrelated packages'
if not sys.argv[1:]:unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([assets[0]])
print(json.dumps(receipt,indent=2))
