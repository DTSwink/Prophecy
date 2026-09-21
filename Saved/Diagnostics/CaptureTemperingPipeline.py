import unreal, pathlib, json, time
base=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureThighOutward.py'
exec(base.read_text().split('knee_foot_alignment_capture=')[0])
class TemperingPipelineCapture(KneeFootAlignmentCapture):
    def __init__(self):
        self.trace=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'
        self.trace.parent.mkdir(parents=True,exist_ok=True)
        self.offset=self.trace.stat().st_size if self.trace.exists() else 0
        self.old=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames')
        ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames 400')
        super().__init__()
    def finish(self,error=None):
        if self.done:return
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(self.old))
        if self.trace.exists():
            with self.trace.open('rb') as f:
                f.seek(self.offset); (self.out/'pipeline.jsonl').write_bytes(f.read())
        super().finish(error)
knee_foot_alignment_capture=TemperingPipelineCapture()
