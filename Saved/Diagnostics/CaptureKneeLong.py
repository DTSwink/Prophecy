import pathlib,unreal
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureTemperingPipeline.py').read_text())
knee_foot_alignment_capture.target_frames=1200
unreal.SystemLibrary.execute_console_command(knee_foot_alignment_capture.ed.get_editor_world(),'Prophecy.NNInputTraceFrames 800')
