import pathlib,unreal
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePelvisHitch.py').read_text().split('pelvis_hitch_capture=')[0])
class NoTemperingCapture(PelvisHitchCapture):
    def tick(self,dt):
        super().tick(dt)
        if self.done:return
        w=self.ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if isinstance(a,unreal.ProphecyAgent) and self.n>=148:
            unreal.ProphecyLowerTemperingLibrary.set_locomotion_lower_body_tempering(a,False)
        if self.n>=240:self.finish()
pelvis_hitch_capture=NoTemperingCapture()
