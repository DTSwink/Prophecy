"""Preserve the agent, load the camera change, and verify reflection without rewiring."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
out = root / 'Saved/Diagnostics/LocomotionCamera20261026'
out.mkdir(parents=True, exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world():
    raise RuntimeError('Active user Play is preserved; loading requires stopped Play.')
world = editor.get_editor_world()
bp_path = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
graph = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'

def audit():
    unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Sword.AuditCollisionGraph')
    return graph.read_text(encoding='utf-16')

if '--build' in sys.argv:
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        if package.get_path_name() == bp_path:
            source = root / 'Content' / (bp_path[6:] + '.uasset')
            backup = out / 'agent-before-save.uasset'
            if not backup.exists():
                shutil.copy2(source, backup)
            if not unreal.EditorLoadingAndSavingUtils.save_packages([package], False):
                raise RuntimeError('Could not preserve current agent edits.')
    if not (out / 'graph-before.txt').exists():
        (out / 'graph-before.txt').write_text(audit(), encoding='utf-8')
        paths = ['Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset', 'Content/testNN.umap']
        (out / 'asset-hashes.json').write_text(json.dumps({p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}, indent=2), encoding='utf-8')
    unreal.SystemLibrary.execute_console_command(world, 'LiveCoding.Compile')
    print('Preserved agent edits; incremental Live Coding requested. Editor stays open.')
elif '--tests' in sys.argv:
    unreal.SystemLibrary.execute_console_command(world,
        'Automation RunTests Prophecy.Camera.LocomotionBlend+Prophecy.Camera.AttackOffsetFade+Prophecy.Camera.COMAndPlayerRig+Prophecy.Robotics.AgentSwitch')
    print('Requested four focused camera/locomotion tests in transient worlds; no user Play or asset changes.')
else:
    function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyLocomotionTypeLibrary:SetLocomotionCameraBlend')
    if not function:
        raise RuntimeError('New camera node is not loaded.')
    if unreal.EditorAssetLibrary.get_metadata_tag(function, 'DefaultToSelf') != 'Agent':
        raise RuntimeError('Camera node lost its Self default.')
    before = (out / 'graph-before.txt').read_text(encoding='utf-8')
    after = audit()
    import re
    def normalize(text):
        return re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+?)_\d+', r'/Script/GameAnimationSample3.Default__\1', text)
    if normalize(before) != normalize(after):
        (out / 'graph-after.txt').write_text(after, encoding='utf-8')
        raise RuntimeError('Blueprint graph changed; review before saving anything.')
    unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    if 'status=3' not in report or 'native_properties=0 pin_types=0' not in report:
        raise RuntimeError('Blueprint type verification failed: ' + report)
    hashes = json.loads((out / 'asset-hashes.json').read_text(encoding='utf-8'))
    if not all(hashlib.sha256((root/p).read_bytes()).hexdigest() == h for p, h in hashes.items()):
        raise RuntimeError('Saved user assets changed during loading; review needed.')
    result = dict(map=world.get_path_name(), node=function.get_path_name(), default_to_self=True,
                  blend_in=unreal.EditorAssetLibrary.get_metadata_tag(function, 'CPP_Default_BlendIn'),
                  blend_out=unreal.EditorAssetLibrary.get_metadata_tag(function, 'CPP_Default_BlendOut'),
                  graph_preserved=True, saved_assets_preserved=True, editor_restarted=False)
    (out / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
