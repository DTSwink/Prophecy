import unreal, json, traceback
class KneeTargets:
    def __init__(self):
        self.rows=[]
        self.cb=unreal.register_slate_post_tick_callback(self.tick)
    def finish(self,error=None):
        unreal.unregister_slate_post_tick_callback(self.cb)
        (kick_knee_capture.out/'target-check.json').write_text(json.dumps({'rows':self.rows,'error':error},default=str))
        print('Knee target check finished',len(self.rows),error)
    def tick(self,dt):
        try:
            w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not w:self.finish();return
            a=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.get_name().endswith('_C_1'))
            pose=a.read_nn_future_world_pose()
            if pose:
                names,future,presented,alpha=pose
                lookup={str(n):i for i,n in enumerate(names)}
                bones={}
                for bone in ('pelvis','thigh_l','calf_l','foot_l'):
                    i=lookup[bone]
                    ts=[future[i],presented[i],a.get_pose_reference_mesh().get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)]
                    bones[bone]=[{'p':[t.translation.x,t.translation.y,t.translation.z],'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]} for t in ts]
                self.rows.append({'n':kick_knee_capture.n,'attack':a.get_nn_attack_state(),'alpha':alpha,'bones':bones})
            if len(self.rows)>=120:self.finish()
        except Exception:self.finish(traceback.format_exc())
knee_targets=KneeTargets()
