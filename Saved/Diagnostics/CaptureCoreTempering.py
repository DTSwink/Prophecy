import unreal,json,time,traceback
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Preserve user Play'
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text(encoding='utf-8')
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')", '')
source=source.replace("'HandChain-'", "'CoreTempering-'")
exec(source.replace('hand_chain_capture=HandChainCapture()',''),globals())
class CoreCapture(HandChainCapture):
    def __init__(self):
        cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyCoreTemperingLibrary')
        self.lib=unreal.get_default_object(cls)
        super().__init__()
    def tick(self,dt):
        super().tick(dt)
        if self.frame>=360:return
        try:
            w=self.ed.get_game_world()
            if not w:return
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                if a.has_valid_agent_handle():
                    self.lib.call_method('SetLocomotionFKCoreTempering',args=(a,True,0.))
        except Exception:self.finish(traceback.format_exc())
core_capture=CoreCapture()
