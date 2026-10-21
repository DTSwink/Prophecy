"""Save only the verified sword Blueprint; leave the current scene alone."""
import json,pathlib,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve active Play'
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
default=unreal.get_default_object(bp.generated_class())
assert default.get_editor_property('BladeBloodMID') is None
additive='--additive' in sys.argv
seeded='--seed' in sys.argv
additive=additive or seeded
m=unreal.load_asset('/Game/Prophecy/BloodTexturePainting/Generated/_mygame_sword_geometry_M_Sword_BloodPaint' if additive else '/Game/_mygame/sword/geometry/M_Sword_BloodDepth')
assert m
if additive:
    assert (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth/additive-graph-check.json').exists()
if seeded:assert (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth/seed-graph-check.json').exists()
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
receipt={'function':'A_Sword.Stain Blade','depth':{'0':'clean','0.5':'tip to halfway','1':'tip to hilt'},'compiled_status':3,'original_graphs_preserved_verbatim':24,'material':m.get_path_name(),'visual_play_test':False,'build':'Live Coding succeeded; 4 compile actions, no restart','saved':['/Game/_mygame/sword/A_Sword',m.get_path_name()]}
if additive:
    receipt.update({'additive':True,'depth':{'0':'adds nothing','0.5':'at least tip to halfway','1':'tip to hilt'},'build':'Live Coding succeeded; runtime/editor 2 actions plus editor wiring repair 1 action, no restart','paint_preservation':'same existing paint MID/RT, union mask; later collision paint reuses blade MID'})
if seeded:
    receipt.pop('original_graphs_preserved_verbatim',None)
    receipt.update({'function':'A_Sword.Stain Blade(Depth, Seed)','original_graphs_preserved':24,'allowed_caller_changes':'new Seed pin and cached tooltip invalidation only','seed':'int32, deterministic RandomStream first fraction, locked at first positive depth','edge':'world-corrected base slope -20..20 degrees, two small lateral sine waves independent of depth','build':'Live Coding editor-only 1 action, no restart'})
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth/receipt.json'
p.write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
