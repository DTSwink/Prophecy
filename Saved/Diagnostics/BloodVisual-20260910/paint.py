import builtins,unreal,json,sys
s=builtins._blood_visual;manager=s['manager']
w=s['world']
names=sys.argv[1:] or list(s['meshes'])
for name in names:
 c=s['meshes'][name];a=c.get_owner();center,extent=a.get_actor_bounds(False)
 locations=[]
 if isinstance(c,unreal.SkeletalMeshComponent):
  locations=[(bone,c.get_socket_location(bone)) for bone in ('head','spine_03','upperarm_l','calf_r')]
 else:
  locations=[('center',center),('upper',center+unreal.Vector(extent.x*.25,0,extent.z*.3))]
 result=[]
 for bone,point in locations:
  start=point+unreal.Vector(0,-max(extent.y*3,200),0);end=point+unreal.Vector(0,max(extent.y*3,200),0)
  hit=unreal.SystemLibrary.line_trace_single(w,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[manager],unreal.DrawDebugTrace.NONE,True)
  if not hit:result.append({'region':bone,'hit':False});continue
  details={}
  for field in ('component','bone_name','face_index','impact_point'):
   try:details[field]=str(hit.get_editor_property(field))
   except Exception as e:details[field]=str(e)
  accepted=manager.try_paint_from_hit(hit,8 if name=='character' else 15,1,-1)
  result.append({'region':bone,'accepted':accepted,'hit':str(hit),'details':str(details)})
 manager.flush_pending_blood_stamps()
 s['report']['cases'][name]['paint']=result
s['report']['stats']=manager.get_debug_stats_string()
(s['out']/'paint.json').write_text(json.dumps(s['report'],indent=2))
print('BLOOD_PAINT',json.dumps(s['report']))
