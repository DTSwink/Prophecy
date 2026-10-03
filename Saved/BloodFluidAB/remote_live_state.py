import sys, time, json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
remote=remote_execution.RemoteExecution(); remote.start(); time.sleep(1.0)
if not remote.remote_nodes:
    print('NO_NODES'); remote.stop(); raise SystemExit(2)
remote.open_command_connection(remote.remote_nodes[0]['node_id'])
code=r'''
import unreal, json
out=[]
try:
    subsystem=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    ew=subsystem.get_editor_world()
except Exception:
    ew=unreal.EditorLevelLibrary.get_editor_world()
worlds=[ew]
# Probe PIE worlds by iterating actors and recording unique worlds.
seen=set([ew.get_path_name() if ew else ''])
try:
    for a in unreal.ActorIterator():
        w=a.get_world()
        if w and w.get_path_name() not in seen:
            if 'PIE' in w.get_path_name() or 'UEDPIE' in w.get_path_name() or w.world_type.name in ('PIE','GAME'):
                worlds.append(w); seen.add(w.get_path_name())
except Exception as e:
    out.append({'actor_iterator_error': repr(e)})
for w in worlds:
    if not w: continue
    winfo={'world':w.get_path_name(),'world_type':getattr(w,'world_type',None).name if hasattr(w,'world_type') else None,'actors':[]}
    try:
        actors=list(unreal.ActorIterator(w))
    except Exception as e:
        actors=[]; winfo['iter_error']=repr(e)
    for a in actors:
        name=a.get_name()
        cls=a.get_class().get_name()
        if 'ProphecyBloodFluidPostProcessController' in cls or 'NiagaraActor' in cls or 'DecalManager' in cls or 'WorldSettings' in cls:
            rec={'name':name,'label':a.get_actor_label() if hasattr(a,'get_actor_label') else name,'class':cls,'path':a.get_path_name(),'hidden':a.is_hidden(),'hidden_ed': False}
            try: rec['hidden_ed']=a.is_hidden_ed()
            except Exception: pass
            comps=[]
            try: cs=a.get_components_by_class(unreal.NiagaraComponent)
            except Exception: cs=[]
            for c in cs:
                asset=None
                try: asset=c.get_asset()
                except Exception: pass
                if asset and asset.get_name()=='NS_bloodsplat':
                    comps.append({'path':c.get_path_name(),'active':c.is_active(),'visible':c.is_visible(),'hidden_game':c.get_editor_property('hidden_in_game'),'custom_depth':c.get_editor_property('render_custom_depth'),'stencil':c.get_editor_property('custom_depth_stencil_value'),'mainpass':c.get_editor_property('render_in_main_pass'),'depthpass':c.get_editor_property('render_in_depth_pass')})
            if comps: rec['blood_comps']=comps
            try:
                pp=a.get_component_by_class(unreal.PostProcessComponent)
                if pp:
                    rec['pp_enabled']=pp.get_editor_property('enabled')
                    rec['pp_blend_weight']=pp.get_editor_property('blend_weight')
                    rec['pp_priority']=pp.get_editor_property('priority')
                    rec['pp_unbound']=pp.get_editor_property('unbound')
                    wb=pp.get_editor_property('settings').weighted_blendables.array
                    rec['blendables']=[{'weight':x.weight,'object':x.object.get_path_name() if x.object else None,'class':x.object.get_class().get_name() if x.object else None,'outer':x.object.get_outer().get_path_name() if x.object and x.object.get_outer() else None} for x in wb]
                    for prop in ['blur_radius','threshold','softness','blur_sample_quality','blood_fluid_post_enabled','show_stencil_debug','update_parameters_every_tick']:
                        try: rec[prop]=a.get_editor_property(prop)
                        except Exception: pass
            except Exception as e:
                rec['pp_error']=repr(e)
            winfo['actors'].append(rec)
    out.append(winfo)
print('PROPHECY_LIVE_STATE='+json.dumps(out))
'''
res=remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print(json.dumps(res))
remote.stop()
