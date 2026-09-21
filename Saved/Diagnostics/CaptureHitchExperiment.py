import pathlib,unreal,sys
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePelvisHitch.py').read_text().split('pelvis_hitch_capture=')[0])
class ExperimentCapture(PelvisHitchCapture):
    def __init__(self,mode,max_frames=600):
        ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ed.get_game_world():raise RuntimeError('Preserving existing Play session; experiments require idle editor')
        self.mode=mode
        self.max_frames=max_frames
        self.oldmode=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportExperiment')
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.SupportExperiment '+str(mode))
        super().__init__()
        (self.out/'experiment.json').write_text(json.dumps({'mode':mode,'old':self.oldmode}))
    def finish(self,error=None):
        if self.done:return
        super().finish(error)
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.SupportExperiment '+str(self.oldmode))
pelvis_hitch_capture=ExperimentCapture(int(sys.argv[1]),int(sys.argv[2]) if len(sys.argv)>2 else 600)
