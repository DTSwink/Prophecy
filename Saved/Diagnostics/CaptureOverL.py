import pathlib,sys,unreal
source=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePelvisHitch.py'
exec(source.read_text().replace('pelvis_hitch_capture=PelvisHitchCapture()',''))
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Need an owned diagnostic session'
class OverLCapture(PelvisHitchCapture):
    max_frames=int(sys.argv[2]) if len(sys.argv)>2 else 360
    def __init__(self):
        self.old_source=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportSource')
        self.old_plane=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.KneePlane')
        self.old_calf=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.CalfContinuity')
        self.changed=set()
        super().__init__()
        if mode=='previous_source':unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.SupportSource 0')
        variant=mode.removeprefix('kick_')
        if variant in ('zero','plane'):
            unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.KneePlane '+str({'zero':0,'plane':1}[variant]))
        (self.out/'variant.txt').write_text(mode)
        if len(sys.argv)>3:
            unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.CalfContinuity '+sys.argv[3])
            (self.out/'variant.txt').write_text(mode+' calf='+sys.argv[3])
    def tick(self,dt):
        w=self.ed.get_game_world()
        if mode.startswith('kick_') and w:
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                state=a.get_nn_attack_state()
                if a.is_player_controlled() and state and str(state[0]).lower()=='overl':
                    target=a.get_nn_attack_target()[0]
                    victim=a.get_nn_attack_victim()
                    assert a.trigger_nn_attack('kickR',target,False,victim)
        if mode=='no_reconstruction' and w and unreal.GameplayStatics.get_time_seconds(w)>1.9:
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                if a.get_name() not in self.changed:
                    unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(a,False)
                    self.changed.add(a.get_name())
        super().tick(dt)
    def finish(self,error=None):
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.SupportSource '+str(self.old_source))
        if self.old_plane is not None:
            unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.KneePlane '+str(self.old_plane))
        if self.old_calf is not None:
            unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.Tempering.CalfContinuity '+str(self.old_calf))
        super().finish(error)
overl_capture=OverLCapture()
