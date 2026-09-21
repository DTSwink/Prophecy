import pathlib,unreal,sys
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePelvisHitch.py').read_text().split('pelvis_hitch_capture=')[0])
class AblationCapture(PelvisHitchCapture):
    def __init__(self,variant,at=150):
        self.variant=variant;self.at=at;super().__init__()
        (self.out/'variant.txt').write_text(variant)
    def tick(self,dt):
        super().tick(dt)
        if self.done:return
        w=self.ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if isinstance(a,unreal.ProphecyAgent) and self.n==self.at:
            try:
                lib=unreal.get_default_object(unreal.ProphecyLowerTemperingLibrary)
                if self.variant=='no_pelvis':result=lib.call_method('BlendLocomotionPelvisTemperingToNormal',(a,0.,0.))
                elif self.variant=='no_feet':result=lib.call_method('BlendLocomotionFeetTemperingToNormal',(a,0.,0.))
                elif self.variant=='no_reconstruction':result=unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(a,False)
                else:raise RuntimeError('Unknown variant')
                assert result, 'Ablation setter failed'
                (self.out/'applied.json').write_text(json.dumps({'variant':self.variant,'tick':self.n,'success':result}))
            except Exception:self.finish(traceback.format_exc());return
        if self.n>=240:self.finish()
pelvis_hitch_capture=AblationCapture(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 150)
