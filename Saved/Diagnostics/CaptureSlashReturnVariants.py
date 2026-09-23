import unreal
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Leave user Play untouched'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text(encoding='utf-8')
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'SlashReturnVariants-'").replace('self.frame>=360','self.frame>=900')
source=source.replace('self.rows=[];self.frame=0;','self.configured=set();self.controlled=set();self.episode=0;self.rows=[];self.frame=0;')
source=source.replace('                pose=a.read_nn_future_world_pose()',
'''                if a.get_name() not in self.configured:
                    assert lib.call_method('SetSlashRightArmReturnToNeutral',args=(a,True,.3,.5,100.))
                    self.configured.add(a.get_name())
                if a.is_player_controlled() and self.frame>=30 and a.get_name() not in self.controlled:
                    a.set_actor_tick_enabled(False)
                    a.stop_nn_attack()
                    self.controlled.add(a.get_name())
                if a.get_name() in self.controlled and self.frame%90==0 and self.frame<900:
                    variants=['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike','slashL','pike']
                    attack=variants[min(self.episode,len(variants)-1)]
                    half=self.episode>=7
                    self.episode+=1
                    target=a.get_actor_location()+a.get_actor_forward_vector()*100.+unreal.Vector(0,0,70)
                    assert a.trigger_nn_attack(attack,target,half,None)
                    print('SLASH_RETURN_VARIANT',self.episode,attack,half)
                pose=a.read_nn_future_world_pose()''')
exec(source,globals())
