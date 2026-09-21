import unreal, json, pathlib, time, traceback
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/OverLArm'
folder.mkdir(exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
trial=sys.argv[1] if len(sys.argv)>1 else 'baseline'
mode=sys.argv[2] if len(sys.argv)>2 else '0,0,1'
attacker_only=len(sys.argv)>3 and sys.argv[3]=='attacker'
end_frame=int(sys.argv[4]) if len(sys.argv)>4 else 600
vel,pos,steps=map(int,mode.split(','))
state={'rows':[],'meta':{},'start':time.monotonic(),'cb':None,'n':0,'owned':not bool(ed.get_game_world()),'mode':mode}
assert state['owned'], 'A trial must start from fresh PIE; preserve existing user play session.'
def vec(v):return [v.x,v.y,v.z]
def done(error=None):
 if error:state['error']=error
 unreal.unregister_slate_post_tick_callback(state['cb'])
 (folder/(trial+'.json')).write_text(json.dumps({k:v for k,v in state.items() if k!='cb'}))
 if state['owned']:level.editor_request_end_play()
 print('OVERL_CAPTURE_DONE',trial,len(state['rows']),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-state['start']>30:done('No play world')
   return
  agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
  if not agents:return
  state['n']+=1
  for a in agents:
   name=a.get_name()
   if name not in state['meta']:
    state['meta'][name]={'location':vec(a.get_actor_location()),'solver':list(a.get_jolt_solver_iterations())}
   if state['n']==30:
    if (vel,pos)!=(0,0) and (not attacker_only or a==unreal.GameplayStatics.get_player_pawn(w,0)):
     result=a.set_jolt_solver_iterations(vel,pos)
     assert result=='', (name,result)
    if steps!=1:unreal.ProphecyJoltBlueprintLibrary.set_jolt_collision_substeps(a,True,steps)
   r={'n':state['n'],'agent':name,'attack':str(a.get_nn_attack_state()),'bodies':{},'solver':list(a.get_jolt_solver_iterations())}
   for b in ['clavicle_l','upperarm_l','lowerarm_l','hand_l','hand_r']:
    p=a.get_physical_body_state(b)
    if p:r['bodies'][b]={'p':vec(p[0].translation),'q':str(p[0].rotation),'v':vec(p[1]),'w':vec(p[2]),'sim':p[3]}
   if state['n']>=30 and 'hand_r' in r['bodies'] and a.is_jolt_physical_animation_enabled():
    xyz=r['bodies']['hand_r']['p']
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment capture '+trial+'_'+name+'_'+str(state['n'])+' at '+' '.join(format(x,'.9f') for x in xyz))
   state['rows'].append(r)
  if state['n']>=end_frame:done()
 except Exception:done(traceback.format_exc())
state['cb']=unreal.register_slate_post_tick_callback(tick)
if state['owned']:level.editor_request_begin_play()
print('OVERL_CAPTURE_STARTED',trial,mode)
