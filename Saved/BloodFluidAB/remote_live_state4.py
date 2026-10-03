import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal,json,traceback,os
out=[]
def as_prop(obj, name, default=None):
    try: return obj.get_editor_property(name)
    except Exception: return default
try:
    editor_world=unreal.EditorLevelLibrary.get_editor_world()
    worlds=[]
    if editor_world: worlds.append(('editor', editor_world))
    try:
        for i,w in enumerate(unreal.EditorLevelLibrary.get_pie_worlds(True)): worlds.append(('pie%d'%i,w))
    except Exception as e: out.append({'get_pie_worlds_error':repr(e)})
    try:
        gw=unreal.EditorLevelLibrary.get_game_world()
        if gw and all(gw.get_path_name()!=w.get_path_name() for _,w in worlds): worlds.append(('game',gw))
    except Exception as e: out.append({'get_game_world_error':repr(e)})
    for label,w in worlds:
        winfo={'label':label,'world':w.get_path_name(),'world_name':w.get_name(),'world_type':str(as_prop(w,'world_type','?')),'actors':[]}
        actors=list(unreal.ActorIterator(w))
        for a in actors:
            cls=a.get_class().get_name(); name=a.get_name()
            blood=[]
            for c in a.get_components_by_class(unreal.NiagaraComponent):
                try: asset=c.get_asset()
                except Exception: asset=None
                if asset and asset.get_name()=='NS_bloodsplat':
                    loc=c.get_world_location()
                    blood.append({'path':c.get_path_name(),'active':c.is_active(),'visible':c.is_visible(),'hidden_game':as_prop(c,'hidden_in_game'),'custom_depth':as_prop(c,'render_custom_depth'),'stencil':as_prop(c,'custom_depth_stencil_value'),'mainpass':as_prop(c,'render_in_main_pass'),'depthpass':as_prop(c,'render_in_depth_pass'),'loc':[round(loc.x,2),round(loc.y,2),round(loc.z,2)]})
            include=blood or 'ProphecyBloodFluidPostProcessController' in cls or 'NiagaraActor' in cls or 'DecalManager' in cls or 'WorldSettings' in cls
            if include:
                try: actor_label=a.get_actor_label()
                except Exception: actor_label=name
                rec={'name':name,'label':actor_label,'class':cls,'path':a.get_path_name(),'hidden':a.is_hidden(),'blood':blood}
                pp=a.get_component_by_class(unreal.PostProcessComponent)
                if pp:
                    rec['pp_enabled']=as_prop(pp,'enabled')
                    rec['pp_blend_weight']=as_prop(pp,'blend_weight')
                    rec['pp_priority']=as_prop(pp,'priority')
                    rec['pp_unbound']=as_prop(pp,'unbound')
                    wb=as_prop(as_prop(pp,'settings'),'weighted_blendables')
                    arr=[]
                    try: arr=wb.array
                    except Exception: pass
                    rec['blendables']=[{'weight':x.weight,'object':x.object.get_path_name() if x.object else None,'class':x.object.get_class().get_name() if x.object else None,'outer':x.object.get_outer().get_path_name() if x.object and x.object.get_outer() else None} for x in arr]
                    for prop in ['blur_radius','threshold','softness','blur_sample_quality','blood_fluid_post_enabled','show_stencil_debug','update_parameters_every_tick']:
                        rec[prop]=as_prop(a,prop,'<missing>')
                winfo['actors'].append(rec)
        out.append(winfo)
except Exception:
    out.append({'fatal':traceback.format_exc()})
path=os.path.join(unreal.Paths.project_saved_dir(),'BloodFluidAB','live_state_dump.json')
with open(path,'w',encoding='utf-8') as f: json.dump(out,f,indent=2)
print('PROPHECY_STATE_FILE='+path)
print('PROPHECY_STATE_SHORT='+json.dumps([{'label':x.get('label'), 'world':x.get('world_name'), 'actors':len(x.get('actors',[]))} for x in out if 'actors' in x]))
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print('success',res.get('success'))
for o in res.get('output',[]): print(o.get('type'), o.get('output',''))
r.stop()
