from pathlib import Path
p=Path('Saved/Diagnostics/FKExit626')
s=(p/'capture.py').read_text(encoding='utf-8-sig').replace("tag='fk_exit626'","tag='fk_exit626_after'").replace("s['frame']>=700","s['frame']>=660")
(p/'capture_after.py').write_text(s,encoding='utf8')
(p/'verify.py').write_text("import unreal\ned=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\nprint('FK_EXIT_CHECKS_USER_PLAY_PRESERVED',bool(ed.get_game_world()))\nunreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.FKReturn+Prophecy.Blends.SixtyTickClock')\n",encoding='utf8')
p=Path('Docs/AttackFKReturn.md');s=p.read_text(encoding='utf8')
marker='## Blueprint controls'
text='''## Exit-interval correction, October 2

The reported slashR hand-velocity interruption around tick626 reproduced at the tick624 handoff in the current scene. Before the exit, right upperarm/lowerarm local rotations advanced 6.7959/10.6054 degrees per policy interval; the first returning interval advanced both by zero. The first new endpoint sampled curve time zero, repeating the outgoing arm pose for two game ticks while the pelvis continued. Captured momentum was present but could not affect that zero-time sample.

The handoff now includes the policy scheduler’s already-spent game ticks since the outgoing publication. Natural exits start the next endpoint at 2/60; explicit stops between boundaries include only the spent portion and consume subsequent ticks normally. The clock is bounded to the remaining original deadline. This changes neither the lab curve nor inertia/profile settings and uses no world-time differences. Snapshot reads keep the original outgoing endpoints; the new sample feeds back through the existing accepted-pose path.

Evidence: `Saved/Diagnostics/FKExit626/` and `Saved/Diagnostics/Knee202/fk_exit626.json`. Source correction complete; loaded-build and post-change verification pending.

'''
assert marker in s;s=s.replace(marker,text+marker,1);p.write_text(s,encoding='utf8')
