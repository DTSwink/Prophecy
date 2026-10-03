import unreal,json,time,traceback
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Leave user Play untouched'
source=Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py'
exec(source.read_text(encoding='utf-8').replace('hand_chain_capture=HandChainCapture()',''),globals())
class SpecialForearms(HandChainCapture):
    def __init__(self):
        self.last_attack={};self.episode=0;self.events=[]
        super().__init__()
    def tick(self,dt):
        super().tick(dt)
        if self.frame>=360:return
        try:
            w=self.ed.get_game_world()
            if not w:return
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            for a in agents:
                attack=a.get_nn_attack_state();name=a.get_name()
                if not attack:self.last_attack[name]=None;continue
                frame=attack[-1];previous=self.last_attack.get(name)
                self.last_attack[name]=frame
                if previous is not None and frame>=previous:continue
                self.episode+=1
                others=[d for d in agents if d!=a and d.has_valid_agent_handle()]
                if not others:continue
                d=min(others,key=lambda b:(b.get_actor_location()-a.get_actor_location()).length())
                half=self.episode>=3
                if half:a.set_nn_half_attack_enabled(True)
                mode='parry' if self.episode%2 else 'dodge'
                fn=unreal.ProphecyNNDefenseLibrary.start_nn_parry if mode=='parry' else unreal.ProphecyNNDefenseLibrary.start_nn_dodge
                result=fn(d,a,3.)
                self.events.append({'episode':self.episode,'mode':mode,'half':half,'result':str(result),'attacker':name,'defender':d.get_name()})
                print('SPECIAL_ROLL_EPISODE',self.events[-1])
        except Exception:self.finish(traceback.format_exc())
    def finish(self,error=None):
        super().finish(error)
        self.out.with_suffix('.events.json').write_text(json.dumps(self.events,indent=2))
special_forearms=SpecialForearms()
