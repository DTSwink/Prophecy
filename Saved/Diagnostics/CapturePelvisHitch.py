import unreal, pathlib, json, time, traceback

class PelvisHitchCapture:
    def __init__(self):
        self.ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.owned=not bool(self.ed.get_game_world())
        self.out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('PelvisHitch-'+time.strftime('%Y%m%d-%H%M%S'))
        self.out.mkdir(parents=True,exist_ok=True)
        self.trace=self.out.parent/'SlashContacts/nn_inputs.jsonl'
        self.offset=self.trace.stat().st_size if self.trace.exists() else 0
        self.old=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames')
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(max(1800,getattr(self,'max_frames',600)*3)))
        self.file=(self.out/'metrics.jsonl').open('w');self.n=0;self.last=None;self.start=time.monotonic();self.done=False;self.info={}
        self.cb=unreal.register_slate_post_tick_callback(self.tick)
        if self.owned:self.level.editor_request_begin_play()
        print('PELVIS_HITCH_CAPTURE',str(self.out),'owns_play',self.owned)
    @staticmethod
    def vec(v):return [v.x,v.y,v.z]
    @staticmethod
    def tr(t):return {'p':[t.translation.x,t.translation.y,t.translation.z],'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]}
    def finish(self,error=None):
        if self.done:return
        self.done=True;unreal.unregister_slate_post_tick_callback(self.cb);self.file.close()
        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(self.old))
        if self.trace.exists():
            with self.trace.open('rb') as f:
                f.seek(self.offset);(self.out/'pipeline.jsonl').write_bytes(f.read())
        (self.out/'summary.json').write_text(json.dumps({'frames':self.n,'owns_play':self.owned,'error':error,'info':self.info},default=str,indent=2))
        if self.owned:self.level.editor_request_end_play()
        print('PELVIS_HITCH_DONE',str(self.out),self.n,error)
    def tick(self,dt):
        try:
            w=self.ed.get_game_world()
            if not w:
                if self.n or time.monotonic()-self.start>45:self.finish('Play unavailable/stopped')
                return
            now=unreal.GameplayStatics.get_time_seconds(w)
            if now==self.last:return
            self.last=now;self.n+=1
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                mesh=a.get_pose_reference_mesh();pose=a.read_nn_future_world_pose()
                if not mesh or not pose:continue
                name=a.get_name();names,future,presented,alpha=pose;lookup={str(b):i for i,b in enumerate(names)}
                if name not in self.info:
                    self.info[name]={'label':a.get_actor_label(),'player':a.is_player_controlled(),'mesh':mesh.get_name()}
                try:tick=a.get_editor_property('tick debug')
                except Exception:tick=None
                bones={}
                for bone in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
                    if bone not in lookup:continue
                    i=lookup[bone];body=a.get_physical_body_state(bone)
                    bones[bone]={'future':self.tr(future[i]),'target':self.tr(presented[i]),'visible':self.tr(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD))}
                    if body:bones[bone].update(body=self.tr(body[0]),velocity=self.vec(body[1]),angular=self.vec(body[2]))
                window=unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
                cube=next((c for c in a.get_components_by_class(unreal.StaticMeshComponent) if 'magic' in c.get_name().lower()),None)
                row={'frame':self.n,'tick':tick,'time':now,'dt':unreal.GameplayStatics.get_world_delta_seconds(w),'agent':name,'attack':a.get_nn_attack_state(),'mode':str(a.get_simulation_mode()),'state':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),'alpha':alpha,'bones':bones,'actor':self.tr(a.get_actor_transform()),'magic':self.vec(unreal.ProphecyRootPhysicsLibrary.get_root_magic_velocity(a)),'magic2':self.vec(unreal.ProphecyRootPhysicsLibrary.get_root_magic_velocity2(a)),'cube':self.vec(cube.get_world_location()) if cube else None,'roots':[self.tr(t) for t in window[0][:3]] if window else None,'loco':str(a.get_locomotion_state()),'tolerance':str(a.get_physical_feedback_tolerance('pelvis')),'magnetisation':str(a.get_body_magnetization_settings('pelvis'))}
                self.file.write(json.dumps(row,default=str)+'\n')
            if self.n%60==0:self.file.flush()
            if self.n>=getattr(self,'max_frames',600) or time.monotonic()-self.start>90:self.finish()
        except Exception:self.finish(traceback.format_exc())

pelvis_hitch_capture=PelvisHitchCapture()
