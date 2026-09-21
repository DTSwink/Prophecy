import unreal, pathlib, json, time, math, traceback

class KneeFootAlignmentCapture:
    def __init__(self):
        self.ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.owned=not bool(self.ed.get_game_world())
        self.out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('ThighOutward-'+time.strftime('%Y%m%d-%H%M%S'))
        self.out.mkdir(parents=True,exist_ok=True)
        self.file=(self.out/'metrics.jsonl').open('w')
        self.n=0;self.start=time.monotonic();self.first=None;self.actors=None;self.shots=set();self.peaks={};self.done=False;self.info={}
        self.cb=unreal.register_slate_post_tick_callback(self.tick)
        if self.owned:self.level.editor_request_begin_play()
        print('KNEE_FOOT_ALIGNMENT',str(self.out),'owns_play',self.owned)
    @staticmethod
    def vec(v):return [v.x,v.y,v.z]
    @staticmethod
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    @staticmethod
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    def norm(self,v):return math.sqrt(self.dot(v,v))
    def metric(self,p):
        h,k,a,t=p
        axis=self.sub(a,h);distance=self.norm(axis)
        if distance<1e-5:return None
        axis=[x/distance for x in axis]
        bend=self.sub(k,h);forward=self.sub(t,a)
        pole=[x-y*self.dot(bend,axis) for x,y in zip(bend,axis)]
        f=[x-y*self.dot(forward,axis) for x,y in zip(forward,axis)]
        radius=self.norm(pole);fl=self.norm(f)
        if radius<3 or fl<1:return None
        angle=math.degrees(math.acos(max(-1,min(1,self.dot(pole,f)/(radius*fl)))))
        ph=math.hypot(pole[0],pole[1]);fh=math.hypot(forward[0],forward[1])
        horizontal=math.degrees(math.acos(max(-1,min(1,(pole[0]*forward[0]+pole[1]*forward[1])/(ph*fh))))) if ph>1 and fh>1 else None
        return {'angle':angle,'horizontal_angle':horizontal,'bend_radius_cm':radius,'chain_distance_cm':distance,'points':p}
    def finish(self,error=None):
        if self.done:return
        self.done=True;unreal.unregister_slate_post_tick_callback(self.cb);self.file.close()
        (self.out/'summary.json').write_text(json.dumps({'frames':self.n,'owns_play':self.owned,'error':error,'peaks':self.peaks,'info':self.info},default=str,indent=2))
        self.actors=None
        if self.owned:self.level.editor_request_end_play()
        print('KNEE_FOOT_ALIGNMENT_DONE',str(self.out),self.n,error)
    def tick(self,dt):
        try:
            w=self.ed.get_game_world()
            if not w:
                if self.first is not None or time.monotonic()-self.start>45:self.finish('Play unavailable/stopped')
                return
            if not self.actors:self.actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            if not self.actors:
                if time.monotonic()-self.start>45:self.finish('No agents found')
                return
            if self.first is None:self.first=time.monotonic()
            self.n+=1
            for a in self.actors:
                if not unreal.SystemLibrary.is_valid(a):continue
                pose=a.read_nn_future_world_pose();mesh=a.get_pose_reference_mesh()
                if not pose or not mesh:
                    self.info[a.get_name()]={'pose':bool(pose),'mesh':bool(mesh)}
                    continue
                names,future,presented,alpha=pose;lookup={str(n):i for i,n in enumerate(names)}
                if a.get_name() not in self.info:self.info[a.get_name()]={'bones':list(lookup),'mesh':mesh.get_name()}
                attack=a.get_nn_attack_state();name=a.get_name()
                for side in ('l','r'):
                    bones=['thigh_'+side,'calf_'+side,'foot_'+side,'ball_'+side]
                    if not all(b in lookup for b in bones[:3]):continue
                    toe_index=mesh.get_bone_index(bones[3])
                    if toe_index<0:raise RuntimeError('Missing authored toe bone '+bones[3])
                    toe_offset=mesh.get_ref_pose_position(toe_index)
                    metrics={};poses={}
                    for source,ts in (('future',future),('presented',presented),('physical',None)):
                        if ts is not None:
                            points=[self.vec(ts[lookup[b]].translation) for b in bones[:3]]
                            points.append(self.vec(unreal.MathLibrary.transform_location(ts[lookup[bones[2]]],toe_offset)))
                        else:
                            points=[self.vec(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD).translation) for b in bones]
                        transforms=[ts[lookup[b]] if ts is not None else mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD) for b in bones[:3]]
                        poses[source]={'points':points,'rotations':[[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w] for x in transforms]}
                        m=self.metric(points)
                        if m:metrics[source]=m
                    row={'frame':self.n,'time':unreal.GameplayStatics.get_time_seconds(w),'agent':name,'side':side,'attack':attack,'mode':str(a.get_simulation_mode()),'alpha':alpha,'metrics':metrics,'poses':poses}
                    self.file.write(json.dumps(row,default=str)+'\n')
                    if self.n>=60:
                        for source,m in metrics.items():
                            key=name+'/'+side+'/'+source
                            if m['angle']>self.peaks.get(key,{}).get('angle',-1):self.peaks[key]={'angle':m['angle'],'frame':self.n,'attack':attack,'horizontal_angle':m['horizontal_angle']}
                        if False:
                            angle=metrics['physical']['angle']
                            for threshold in (60,80,90):
                                key=(name,threshold)
                                if angle>=threshold and key not in self.shots:
                                    self.shots.add(key)
                                    path=str((self.out/(name+'-'+str(threshold)+'-frame'+str(self.n)+'.png')).resolve()).replace('\\','/')
                                    unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+path+'" nosuffix')
            if self.n%120==0:self.file.flush()
            if self.n>=getattr(self,'target_frames',600) or time.monotonic()-self.first>=60:self.finish()
        except Exception:self.finish(traceback.format_exc())

knee_foot_alignment_capture=KneeFootAlignmentCapture()
