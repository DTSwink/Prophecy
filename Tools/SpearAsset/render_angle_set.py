"""Small sequential CPU stills through the existing Blender MCP session."""
import json,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'Exports/ImperialSpear'
PY=ROOT/'Saved/Diagnostics/ImperialSpear/mcp-env/Scripts/python.exe'
jobs=[
 {'name':'Preview_Gold_Detail','azimuth':28,'target':[.013,0,1.744],'scale':.31,'roll':-35,'size':[1100,1000],'samples':24},
 {'name':'Preview_ThreeQuarter','azimuth':48,'target':[.055,0,1.89],'scale':.76,'roll':-30,'size':[1000,1000],'samples':24},
 {'name':'Preview_Back','azimuth':180,'target':[.055,0,1.90],'scale':.76,'roll':30,'size':[1000,1000],'samples':24},
 {'name':'Preview_Recess_Detail','azimuth':35,'target':[0,0,1.95],'scale':.105,'roll':-25,'size':[1000,800],'samples':32},
 {'name':'Preview_Full','azimuth':0,'target':[.04,0,1.1],'scale':2.58,'roll':-43,'elevation':.06,'size':[1400,1000],'samples':24},
]
for job in jobs:
    (OUT/'render_request.json').write_text(json.dumps(job),encoding='utf-8')
    log=ROOT/'Saved/Diagnostics/ImperialSpear'/('render_'+job['name']+'.log')
    with log.open('w',encoding='utf-8') as handle:
        p=subprocess.run([str(PY),str(ROOT/'Tools/SpearAsset/mcp_client.py'),str(ROOT/'Tools/SpearAsset/render_refined.py')],stdout=handle,stderr=handle,cwd=ROOT,timeout=240)
    content=log.read_text(encoding='utf-8')
    if p.returncode or 'Error executing code:' in content: raise RuntimeError(content[-4000:])
    shutil.copyfile(ROOT/'Saved/Diagnostics/ImperialSpear/mcp_render_refined.json',ROOT/'Saved/Diagnostics/ImperialSpear'/('mcp_'+job['name']+'.json'))
    print('Completed '+job['name'],flush=True)
(OUT/'render_request.json').unlink(missing_ok=True)
