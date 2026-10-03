from pathlib import Path
import json
folder=Path('C:/Users/singerie/Documents/Cursor/stepper/training/rollout_debug_viewer')
html=(folder/'turn_parity_temp.html').read_text(encoding='utf-8')
seed=json.loads(Path(__file__).with_name('window_seed.json').read_text())
assert seed.get('upper_root_window_positions')
html=html.replace("return originalFetch('/turn_parity_temp.json',options);",'return new Response('+json.dumps(json.dumps(seed,separators=(',',':')))+",{headers:{'Content-Type':'application/json'}});")
html=html.replace('<script src="/assets/full_visualisation.js?v=3-spine-frames"></script>','<script>'+(folder/'assets/full_visualisation.js').read_text(encoding='utf-8')+'</script>')
html=html.replace('<title>Last Batch Rollout</title>','<title>Upper-body rotation horizon</title>')
html=html.replace('<div id="proofLabel">','''<div id="horizonPanel" style="position:absolute;right:20px;top:20px;z-index:40;background:#151920ed;color:#edf1f5;padding:16px;border:1px solid #454f60;border-radius:8px;width:330px">
<b>Upper-body rotation horizon</b><output id="horizonValue" style="float:right">1.00</output>
<input id="horizonSlider" aria-label="Upper-body rotation horizon" type="range" min="0" max="1" step="0.05" value="1" style="width:100%;margin:14px 0 8px">
<div style="color:#aebccc;font-size:12px">1 = original · 0.5 = first half stretched across the full window · 0 = present rotation throughout.<br>Lower body and root positions stay unchanged.</div>
<button id="horizonRetry" style="margin-top:8px">Retry replay</button><div id="horizonStatus" role="status" style="margin-top:10px;font-size:12px;color:#5eead4">Showing original replay (1.00).</div>
<div style="font-size:11px;color:#aebccc;margin-top:8px">White R0 · cyan→purple R1–R8.<br>Arrow lengths separate overlapping directions; root positions stay exact.</div></div><div id="proofLabel">''')
script='<script>'+Path(__file__).with_name('controls.js').read_text(encoding='utf-8')+'</script>'
html=html.replace('</body>',script+'</body>')
html=html.replace('</head>','<style>#proofLabel,#overlay{display:none!important}</style></head>')
html=html.replace('    function draw() {','    function draw() {\n      if(window.upperHorizonBenchPaused){setTimeout(()=>requestAnimationFrame(draw),500);return;}')
html=html.replace('    function tick(now) {','    function tick(now) {\n      if(window.upperHorizonBenchPaused){lastTime=now;setTimeout(()=>requestAnimationFrame(tick),500);return;}')
# Separate UI preferences and file; the main replay and viewer remain untouched.
html=html.replace('turnParity_','upperHorizon_')
(folder/'turn_upper_horizon_temp.html').write_text(html,encoding='utf-8')
print('http://127.0.0.1:8021/turn_upper_horizon_temp.html')
