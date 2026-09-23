import unreal,json,time,traceback
from pathlib import Path
class HandChainCapture:
    def __init__(self):
        self.ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.owned=not bool(self.ed.get_game_world())
        self.out=Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('HandChain-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        self.rows=[];self.frame=0;self.last=None;self.start=time.monotonic()
        self.cb=unreal.register_slate_post_tick_callback(self.tick)
        if self.owned:self.level.editor_request_begin_play()
        print('HAND_CHAIN_CAPTURE',str(self.out),'owns_play',self.owned)
    def finish(self,error=None):
        unreal.unregister_slate_post_tick_callback(self.cb)
        self.out.write_text(json.dumps({'error':error,'frames':self.frame,'rows':self.rows}))
        if self.owned:self.level.editor_request_end_play()
        print('HAND_CHAIN_CAPTURE_DONE',str(self.out),self.frame,error)
    def tick(self,dt):
        try:
            w=self.ed.get_game_world()
            if not w:
                if self.frame or time.monotonic()-self.start>45:self.finish('Play unavailable/stopped')
                return
            now=unreal.GameplayStatics.get_time_seconds(w)
            if now==self.last:return
            self.last=now;self.frame+=1
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                pose=a.read_nn_future_world_pose()
                if not pose:continue
                names,future,presented,alpha=pose
                def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
                bones={str(n):[tr(future[i]),tr(presented[i])] for i,n in enumerate(names) if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')}
                self.rows.append({'frame':self.frame,'time':now,'agent':a.get_name(),'attack':str(a.get_nn_attack_state()),'state':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),'alpha':alpha,'bones':bones})
            if self.frame>=360 or time.monotonic()-self.start>90:self.finish()
        except Exception:self.finish(traceback.format_exc())
hand_chain_capture=HandChainCapture()
