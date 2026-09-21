import builtins,unreal,sys,json,time,pathlib
s=builtins._blood_visual
phase=sys.argv[1] if len(sys.argv)>1 else 'clean'
names=sys.argv[2:] or list(s['meshes'])
queue=list(names);state={'handle':None,'task':None,'name':None,'start':time.monotonic(),'done':False}
builtins._blood_capture=state
def tick(dt):
 try:
  if state['task'] and not state['task'].is_task_done():return
  if state['name']:
   path=s['out']/(state['name']+'_'+phase+'.png')
   print('BLOOD_IMAGE',str(path),path.exists());state['name']=None
  if not queue:
   unreal.unregister_slate_post_tick_callback(state['handle']);state['done']=True;return
  name=queue.pop(0);state['name']=name
  cam=s['actors']['camera_'+name]
  state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1280,900,str(s['out']/(name+'_'+phase+'.png')),cam,False,False,unreal.ComparisonTolerance.LOW,'Blood receiver '+name+' '+phase,0.3,True)
 except Exception as e:
  state['error']=str(e);print('BLOOD_IMAGE_ERROR',str(e));unreal.unregister_slate_post_tick_callback(state['handle']);state['done']=True
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('BLOOD_IMAGES_QUEUED',names,phase)
