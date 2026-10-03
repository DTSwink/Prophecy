from pathlib import Path
p=Path(__file__).with_name('create_viewer.py')
s=p.read_text(encoding='utf-8')
start=s.index("script='''")
end=s.index("html=html.replace('</body>',script+'</body>')")
s=s[:start]+"script='<script>'+Path(__file__).with_name('controls.js').read_text(encoding='utf-8')+'</script>'\n"+s[end:]
s=s.replace('<div id="horizonStatus" role="status"', '<button id="horizonRetry" style="margin-top:8px">Retry replay</button><div id="horizonStatus" role="status"')
s=s.replace('</div><div id="proofLabel">', '''<div style="font-size:11px;color:#aebccc;margin-top:8px">White R0 · cyan→purple R1–R8.<br>Arrow lengths separate overlapping directions; root positions stay exact.</div></div><div id="proofLabel">''')
s=s.replace("html=html.replace('</body>',script+'</body>')", "html=html.replace('</body>',script+'</body>')\nhtml=html.replace('</head>','<style>#proofLabel,#overlay{display:none!important}</style></head>')")
p.write_text(s,encoding='utf-8')
