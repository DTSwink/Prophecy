import unreal,pathlib,json,time
base=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureThighOutward.py'
exec(base.read_text().split('knee_foot_alignment_capture=')[0])
class KickFloorCapture(KneeFootAlignmentCapture):
 def __init__(self):
  self.trace=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/live_steps.jsonl'
  self.offset=self.trace.stat().st_size if self.trace.exists() else 0
  self.old={k:unreal.SystemLibrary.get_console_variable_int_value(k) for k in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames')}
  ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
  for k,v in [('Prophecy.SlashTraceAgent',-2),('Prophecy.SlashTraceFrames',600)]:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),k+' '+str(v))
  super().__init__()
 def tick(self,dt):
  super().tick(dt)
  if self.n==120 and self.actors:
   config={}
   for a in self.actors:
    props={}
    for p in ('attack_foot_clamp_leeway_cm','attack_calf_clamp_leeway_cm','attack_foot_clamp','attack_calf_clamp','override_attack_foot_clamp','override_attack_calf_clamp'):
     try:props[p]=str(a.get_editor_property(p))
     except Exception as e:props[p]=str(e)
    props['foot_ref']={}
    mesh=a.get_pose_reference_mesh()
    for b in ('foot_l','foot_r','ball_l','ball_r'):
     props['foot_ref'][b]=str(mesh.get_ref_pose_position(mesh.get_bone_index(b)))
    config[a.get_name()]=props
   (self.out/'config.json').write_text(json.dumps(config,indent=2))
 def finish(self,error=None):
  if self.done:return
  for k,v in self.old.items():unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),k+' '+str(v))
  if self.trace.exists():
   with self.trace.open('rb') as f:f.seek(self.offset);(self.out/'slash.jsonl').write_bytes(f.read())
  super().finish(error)
kick_floor_capture=KickFloorCapture()
