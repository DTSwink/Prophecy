import pathlib
src=pathlib.Path('Saved/Diagnostics/CompareHead187.py').read_text().replace("('baseline','repeat','chainoff','armoff')","('baseline','coreearly','corelate')").replace("range(20,171)","range(20,138)").replace("Head187-comparison.json","Head187-core-comparison.json")
exec(compile(src,'CompareHead187Core','exec'))
