"""Plot exported Unreal projector bounds; this is a diagram, not a GPU capture."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

out = Path(__file__).resolve().parents[1] / "Saved" / "Results"
layout = json.loads((out / "footprints.json").read_text())
fig, axes = plt.subplots(4, 2, figsize=(8, 11), sharex=True, sharey=True)
fig.suptitle("Decal projector footprints", fontsize=19, fontweight="bold", y=.98)
fig.text(.5,.947,"Actual component bounds • geometry diagnostic, not a rendered material",
         ha="center", fontsize=9, color="#555555")
names = {"filled":"Filled patch", "hole":"Patch with a hole", "splash":"Scattered impacts", "strip":"Thin strip"}
for row, (shape, pair) in enumerate(layout.items()):
    for col, mode in enumerate(("old","new")):
        ax = axes[row,col]
        rects = pair[mode]
        for x,y,w,h in rects:
            ax.add_patch(Rectangle((x,y),w,h,facecolor="#ba2435",edgecolor="#801322",
                                   alpha=.26,linewidth=.6))
        ax.add_patch(Rectangle((0,0),200,200,facecolor="none",edgecolor="#555555",
                               linewidth=.7,linestyle="--"))
        ax.set_title(f"{names[shape]} · {'Old rule' if mode=='old' else 'New rectangles'} · {len(rects)} decal{'s' if len(rects)!=1 else ''}",
                     fontsize=10)
        ax.set(xlim=(-60,260),ylim=(-60,260),aspect="equal",xticks=(0,100,200),yticks=(0,100,200))
        ax.grid(alpha=.12)
        ax.tick_params(labelsize=8)
        if col==0:
            ax.set_ylabel("cm",fontsize=8)
        if row==3:
            ax.set_xlabel("cm",fontsize=8)
        for spine in ax.spines.values():
            spine.set_color("#bbbbbb")
fig.text(.5,.015,"Darker areas overlap. Dashed box: original 200 × 200 cm fixture extent.",
         ha="center",fontsize=9,color="#555555")
fig.tight_layout(rect=(.02,.035,.98,.935))
fig.savefig(out/"footprints.png",dpi=130)
print(out/"footprints.png")
