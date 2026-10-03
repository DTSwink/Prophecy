import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal,json
out=[]
try:
    editor_world=unreal.EditorLevelLibrary.get_editor_world()
except Exception:
    editor_world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
worlds=[]
if editor_world: worlds.append(('editor', editor_world))
try:
    for i,w in enumerate(unreal.EditorLevelLibrary.get_pie_worlds()):
        worlds.append(('pie%d'%i, w))
except Exception as e:
    out.append({'get_pie_worlds_error':repr(e)})
try:
    gw=unreal.EditorLevelLibrary.get_game_world()
    if gw and all(gw.get_path_name()!=w.get_path_name() for _,w in worlds): worlds.append(('game', gw))
except Exception as e: out.append({'get_game_world_error':repr(e)})
for label,w in worlds:
    winfo={'label':label,'world':w.get_path_name(),'world_name':w.get_name(),'world_type':w.world_type.name,'actors':[]}
    try:
        actors=list(unreal.ActorIterator(w))
    except Exception as e:
        winfo['iter_error']=repr(e); actors=[]
    for a in actors:
        cls=a.get_class().get_name(); name=a.get_name(); lbl=name
        try: lbl=a.get_actor_label()
        except Exception: pass
        include=('ProphecyBloodFluidPostProcessController' in cls or 'NiagaraActor' in cls or 'DecalManager' in cls or 'WorldSettings' in cls)
        rec=None
        blood=[]
        try: comps=a.get_components_by_class(unreal.NiagaraComponent)
        except Exception: comps=[]
        for c in comps:
            asset=None
            try: asset=c.get_asset()
            except Exception: pass
            if asset and asset.get_name()=='NS_bloodsplat':
                blood.append({'path':c.get_path_name(),'active':c.is_active(),'visible':c.is_visible(),'hidden_game':c.get_editor_property('hidden_in_game'),'custom_depth':c.get_editor_property('render_custom_depth'),'stencil':c.get_editor_property('custom_depth_stencil_value'),'mainpass':c.get_editor_property('render_in_main_pass'),'depthpass':c.get_editor_property('render_in_depth_pass'),'loc':tuple(round(v,2) for v in [c.get_world_location().x,c.get_world_location().y,c.get_world_location().z])})
        if blood or include:
            rec={'name':name,'label':lbl,'class':cls,'path':a.get_path_name(),'hidden':a.is_hidden(),'blood':blood}
            try: rec['hidden_ed']=a.is_hidden_ed()
            except Exception: pass
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
            except Exception as e: rec['pp_error']=repr(e)
            winfo['actors'].append(rec)
    out.append(winfo)
print('PROPHECY_STATE='+json.dumps(out))
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
for o in res.get('output',[]): print(o.get('output',''))
r.stop()
