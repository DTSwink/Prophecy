"""Link all strap constraints to the current first joint; preserve joint geometry."""
import unreal,pathlib,shutil,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
r=pathlib.Path(unreal.Paths.project_dir()).resolve();out=r/'Saved/Diagnostics/HolsterStrap20261013'
bp=unreal.load_asset('/Game/_mygame/assets/holster/Animated/ABP_HolsterStrap');assert bp
backup=out/'ABP_HolsterStrap-before-linked-limits.uasset'
if not backup.exists():shutil.copy2(r/'Content/_mygame/assets/holster/Animated/ABP_HolsterStrap.uasset',backup)
def command(args):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.HolsterAnimBlueprint '+args)
 return (out/'anim-blueprint.txt').read_text(encoding='utf-8-sig')
before=command('Inspect');(out/'limits-before.txt').write_text(before,encoding='utf-8')
after=command('LinkLimits TestLinks Open')
assert 'shared_constraints=1' in after and 'shared_edit_event_test=PASS' in after,after
def geometry(report):return [line.split(' box=')[1] for line in report.splitlines() if line.startswith('body=')]
assert geometry(before)==geometry(after),'Never copy size or joint pivots'
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
verified=command('Inspect');assert 'status=3' in verified and 'shared_constraints=1' in verified
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
(out/'linked-limits-test.txt').write_text(after,encoding='utf-8')
print('LINKED_STRAP_CONSTRAINTS',verified)
