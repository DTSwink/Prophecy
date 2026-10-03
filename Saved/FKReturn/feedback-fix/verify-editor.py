import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/feedback-fix'
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RefreshFKReturn')
pins=(root/'Saved/Diagnostics/FKReturnAlphaHoldPins.txt').read_text(encoding='utf-8-sig')
assert 'nodes=1 values_and_links_preserved=1 status=3' in pins,pins
exec((root/'Tools/NN/VerifyFKReturnEditor.py').read_text(),globals())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(out/'graph-after.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
scene={a.get_path_name():str(a.get_actor_transform()) for a in actors}
(out/'scene-after.json').write_text(json.dumps(scene,indent=2))
import re
def stable(values):return {k:re.sub(r'0x[0-9A-Fa-f]+','PTR',v) for k,v in values.items()}
assert stable(scene)==stable(json.loads((out/'scene-before.json').read_text())),'Scene changed'
(out/'editor-check.json').write_text(json.dumps({'pins':pins,'scene_unchanged':True,'play':False},indent=2))
print('FK_FEEDBACK_EDITOR_CHECK_PASSED')
