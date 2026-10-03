"""Display the autonomous Python replay in a temporary copy of the local Replayer."""
import runpy,json
from pathlib import Path
g=runpy.run_path(str(Path(__file__).with_name('CompareTurnLower.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
from datetime import datetime,timezone
v=np.load(base/'coupled_4.npz');n=len(v['times']);lower=torch.tensor(v['lower']);upper=torch.tensor(v['upper']);rootinfo=rootinfo[:n]
with torch.inference_mode():
 a=rootinfo[:,7]-rootinfo[:,11];b=torch.eye(3).repeat(n,1,1);b[:,0,0]=a.cos();b[:,0,2]=a.sin();b[:,2,0]=-a.sin();b[:,2,2]=a.cos();b=seed@b@seed.T
 for off in [0,9,25]:lower[:,off:off+3]=(lower[:,off:off+3].unsqueeze(1)@b).squeeze(1)
 for off in [3,12,18,28,34]:lower[:,off:off+6]=tl.rotmat_to_6d(tl.rotation_6d_to_matrix(lower[:,off:off+6])@b)
 a=rootinfo[:,7];heading=torch.eye(3).repeat(n,1,1);heading[:,0,0]=a.cos();heading[:,0,2]=-a.sin();heading[:,2,0]=a.sin();heading[:,2,2]=a.cos()
 rootrot=seed@heading;rootpos=rootinfo[:,4:7].clone();rootpos[:,0]-=rootpos[0,0].item();rootpos[:,2]-=rootpos[0,2].item()
 pelvis=rt.pelvis_heading_features(lower,rootrot,heading)
 p,q=ctl.decode_rows(runtime,1.,lower,upper,pelvis,rootpos,rootrot,heading,torch.zeros(n,dtype=torch.long))
 # Independently decoded autonomous replay remains matched to the earlier checked decode.
 reference=np.load(base/'ue_training_decoded.npz');qe=np.max(abs(q.numpy()-reference['rotations'][:n]));print('autonomous vs checked decode matrix max',qe)
 assert qe<.0001
 clip=runtime.full_by_mode[1.];selections=[np.flatnonzero((v['times']>=7.55)&(v['times']<9.95)),np.arange(n)]
 labels=['Python replay: settled turn at 8 s (loops)','Python replay: full 12 s, including warm-up']
 payload=dict(schema_version=2,computed_at=datetime.now(timezone.utc).isoformat(),run_id='Python reproduction - UE inputs',step=70750,fps=30,joint_names=list(clip.body_names),bones=[[int(parent),i] for i,parent in enumerate(clip.parents_body_list) if int(parent)>=0],rows=[],positions=[],basis=[],controller_root_pos=[],controller_root_rot=[],source_frame=[],source_clip_name=[],lower_pin_probabilities=[],lower_pin_probability_names=['left','right'],metadata=dict(capture_source='independent_python_autoregression',checkpoint=c['checkpoint_path'],gaze_normalized=[0,0]),message='Independent Python lower + upper replay. Same root inputs and initial history as UE; no UE pose playback.')
 for i,s in enumerate(selections):
  payload['rows'].append(dict(row=i,clip_id=i,clip_name=labels[i],start=int(s[0]),effective_k=len(s)-1,virtual=False,noisy=False,has_sword=True,locomotion_category='walk',gaze_normalized=[0,0]))
  for key,value in [('positions',p.numpy()),('basis',q.numpy()),('controller_root_pos',rootpos.numpy()),('controller_root_rot',rootrot.numpy()),('lower_pin_probabilities',v['pins'])]:payload[key].append(value[s].tolist())
  payload['source_frame'].append(s.tolist());payload['source_clip_name'].append([labels[i]]*len(s))
 folder=stepper/'training/rollout_debug_viewer';(folder/'turn_parity_temp.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
 html=(folder/'viewer.html').read_text(encoding='utf-8')
 shim='''<script>
const originalFetch=window.fetch.bind(window);
window.fetch=async (input,options)=>{
 const url=new URL(typeof input==='string'?input:input.url,location.href);
 const value=url.pathname==='/api/experiments'?{runs:[{run_id:'Python reproduction - UE inputs',has_debug_rollout:true,rollout_count:1,is_running:false}]}:
 url.pathname==='/api/rollouts'?{rollouts:[]}:
 url.pathname==='/api/config'?{source:'Independent Python replay; no training process is running'}:null;
 if(value)return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
 if(url.pathname==='/api/rollout')return originalFetch('/turn_parity_temp.json',options);
 if(options&&options.method==='POST')return new Response('{}',{status:403});
 return originalFetch(input,options);
};
</script><style>#sideTools,#flagsBtn,#topRefreshBtn,#contextMenu{display:none!important}#proofLabel{position:absolute;left:20px;bottom:20px;max-width:650px;background:#151920e8;color:#edf1f5;padding:10px 14px;pointer-events:none;font-size:13px;line-height:1.6;border-radius:6px}#proofLabel b{color:#f3b55f}</style>
'''
 html=html.replace('<title>Rollout Replayer</title>','<title>Python turn replay — reproduced overshoot</title>').replace('<h1>Rollout Replayer</h1>','<h1>Python turn replay</h1>')
 html=html.replace('<script src="/assets/full_visualisation.js?v=3-spine-frames"></script>',shim+'<script src="/assets/full_visualisation.js?v=3-spine-frames"></script>')
 html=html.replace('<div id="empty">','<div id="proofLabel"><b>Independent Python replay · gaze 0,0</b><br>Settled turn around simulation time 8 s. Watch the head brim turn past its final direction, then return.<br>Space: pause · ←/→: step · drag: orbit · wheel: zoom · speed below. Loop reset occurs at the end.</div><div id="empty">')
 html=html.replace('<input id="fullVisualisationToggle" type="checkbox">','<input id="fullVisualisationToggle" type="checkbox" checked>')
 html=html.replace('fullVisualisationToggle.checked = localStorage.getItem("replayerFullVisualisation") === "1";','fullVisualisationToggle.checked = true;')
 html=html.replace('colliderHighlightsToggle.checked = localStorage.getItem("replayerColliderHighlights") !== "0";','colliderHighlightsToggle.checked = false;')
 for key in ['replayerFullVisualisation','replayerColliderHighlights','rolloutDebugSidebarClosed']:html=html.replace('"'+key+'"','"turnParity_'+key+'"')
 html=html.replace('refreshRollout(false, latest)\n        );','refreshRollout(false, latest).then(() => { speedSelect.value="1"; distance=3.8; target=[0,0.9,0]; yaw=-0.6; pitch=-0.22; setPlaying(true); })\n        );')
 html=html.replace('setSidebarClosed(localStorage.getItem("rolloutDebugSidebarClosed") === "1");','setSidebarClosed(true);')
 (folder/'turn_parity_temp.html').write_text(html,encoding='utf-8')
 print('READY http://127.0.0.1:8021/turn_parity_temp.html',len(selections[0]),'frames in focus loop')
