import unreal, pathlib, json, time, math, traceback

class KickKneeCapture:
    def __init__(self):
        self.ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.owned=not bool(self.ed.get_game_world())
        self.out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('KickKnee-'+time.strftime('%Y%m%d-%H%M%S'))
        self.out.mkdir(parents=True,exist_ok=True)
        self.rows=[];self.n=0;self.start=time.monotonic();self.first=None;self.agents=None;self.shots=0;self.previous={};self.events=[]
        self.cb=unreal.register_slate_post_tick_callback(self.tick)
        if self.owned:self.level.editor_request_begin_play()
        print('KNEE_CAPTURE',str(self.out),'owns_play',self.owned)
    def vec(self,v):return [v.x,v.y,v.z]
    def quat(self,q):return [q.x,q.y,q.z,q.w]
    def shot(self,w,label):
        path=str((self.out/(label+'.png')).resolve()).replace('\\','/')
        unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+path+'" nosuffix')
    def finish(self,error=None):
        unreal.unregister_slate_post_tick_callback(self.cb)
        (self.out/'capture.json').write_text(json.dumps({'rows':self.rows,'events':self.events,'error':error},default=str))
        (self.out/'done.json').write_text(json.dumps({'frames':self.n,'events':len(self.events),'error':error}))
        if self.owned:self.level.editor_request_end_play()
        print('KNEE_CAPTURE_DONE',str(self.out),self.n,error)
    def tick(self,dt):
        try:
            w=self.ed.get_game_world()
            if not w:
                if self.first is not None or time.monotonic()-self.start>45:self.finish('Play stopped or unavailable')
                return
            if self.first is None:self.first=time.monotonic()
            if self.agents is None:self.agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            self.n+=1
            if self.n in (60,900,2400,4800):self.shot(w,'view-'+str(self.n))
            for a in self.agents:
                if not unreal.SystemLibrary.is_valid(a):continue
                row={'n':self.n,'time':unreal.GameplayStatics.get_time_seconds(w),'agent':a.get_name(),'attack':a.get_nn_attack_state(),'mode':str(a.get_simulation_mode()),'meshes':{}}
                for name,m in [('target',a.get_agent_mesh()),('visible',a.get_pose_reference_mesh())]:
                    if not m or m.get_num_bones()==0:continue
                    data={}
                    for bone in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
                        t=m.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)
                        data[bone]={'p':self.vec(t.translation),'q':self.quat(t.rotation)}
                    row['meshes'][name]=data
                    # Detect large single-frame calf rotation; save the actual viewport too.
                    q=data['calf_l']['q'];key=(a.get_name(),name)
                    old=self.previous.get(key)
                    if old:
                        angle=math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(q,old))))))
                        if angle>30:
                            self.events.append({'n':self.n,'agent':key[0],'mesh':name,'calf_jump_deg':angle,'attack':row['attack']})
                            if name=='visible' and self.shots<8:
                                self.shot(w,'jump-'+str(self.n));self.shots+=1
                    self.previous[key]=q
                self.rows.append(row)
            if time.monotonic()-self.first>=150 or self.n>=12000:self.finish()
        except Exception:self.finish(traceback.format_exc())

kick_knee_capture=KickKneeCapture()
