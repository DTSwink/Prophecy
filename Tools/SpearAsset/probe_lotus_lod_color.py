import bpy,json,math
ob=bpy.data.scenes['GAME • Unreal export'].objects['SM_ImperialSpear_LOD1']
colors=[tuple(c.color) for c in ob.data.color_attributes['PommelCavity'].data]
print(json.dumps({'min':[min(c[i] for c in colors) for i in range(4)],'max':[max(c[i] for c in colors) for i in range(4)],'nonfinite':sum(not all(math.isfinite(v) for v in c) for c in colors),'bad':[c for c in colors if not(.45-1e-6<=c[0]<=1+1e-6 and abs(c[3]-1)<1e-6 and max(abs(c[0]-c[i]) for i in (1,2))<1e-6)][:12]}))
