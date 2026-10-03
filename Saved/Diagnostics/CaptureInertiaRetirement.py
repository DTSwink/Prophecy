import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CapturePelvisHitch.py').read_text().replace("getattr(self,'max_frames',600)","480").replace("'PelvisHitch-'","'InertiaRetirement-'")
# Preserve the first attack/handoff/exit. Stop later authored retriggers only,
# so the first 300-tick inertia window can reach its original deadline.
src=src.replace("mesh=a.get_pose_reference_mesh();pose=a.read_nn_future_world_pose()", """if self.n==200 and a.is_player_controlled():a.set_actor_tick_enabled(False)
                mesh=a.get_pose_reference_mesh();pose=a.read_nn_future_world_pose()""")
exec(compile(src,'CaptureInertiaRetirement','exec'))
