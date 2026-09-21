import pathlib,unreal,sys
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePelvisHitch.py').read_text().split('pelvis_hitch_capture=')[0])
class SupportSourceCapture(PelvisHitchCapture):
    def __init__(self,enabled,max_frames):
        ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ed.get_game_world():raise RuntimeError('Preserving active Play; capture requires idle editor')
        self.max_frames=max_frames
        self.old_source=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportSource')
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.SupportSource '+str(enabled))
        super().__init__()
        (self.out/'support_source.json').write_text(json.dumps({'enabled':enabled,'old':self.old_source}))
    def finish(self,error=None):
        if self.done:return
        super().finish(error)
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.SupportSource '+str(self.old_source))
pelvis_hitch_capture=SupportSourceCapture(int(sys.argv[1]),int(sys.argv[2]) if len(sys.argv)>2 else 600)
