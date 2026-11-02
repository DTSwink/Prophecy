"""Historical Matplotlib diagnostic only. DO NOT use for occlusion/pose review: mplot3d depth sorting is incorrect for overlapping colliders. Use arm_viewer instead."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from repair_slow_targets import Geometry,OUT

def draw(ax,g,p,r,title,azim=-50):
    g.set_pose(p,r)
    colors=['#8696a8']*len(g.gs)
    for i,b in enumerate(g.gb):
        if b in (3,4,5):colors[i]='#e46a33'
        if b in (6,7,8):colors[i]='#f0b23d'
    for i,geom in enumerate(g.gs):
        c=g.d.geom_xpos[i];rot=g.d.geom_xmat[i].reshape(3,3);s=geom['size']
        if geom['type']=='capsule':
            t=np.linspace(0,2*np.pi,20);v=np.linspace(0,np.pi,16)
            x=s[0]*np.outer(np.sin(v),np.cos(t));y=s[0]*np.outer(np.sin(v),np.sin(t))
            z=np.repeat((s[0]*np.cos(v)+s[1]*np.sign(np.cos(v)))[:,None],len(t),axis=1)
            a=np.stack([x,y,z],-1)@rot.T+c
            ax.plot_surface(a[:,:,0],a[:,:,1],a[:,:,2],color=colors[i],linewidth=0,alpha=.92)
        else:
            corners=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])*s
            corners=corners@rot.T+c
            faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]
            ax.add_collection3d(Poly3DCollection([corners[f] for f in faces],facecolor=colors[i],edgecolor='#555555',linewidth=.3))
    mid=p[0];ax.set_xlim(mid[0]-.65,mid[0]+.65);ax.set_ylim(mid[1]-.65,mid[1]+.65);ax.set_zlim(0,1.3)
    ax.set_box_aspect((1,1,1));ax.view_init(18,azim);ax.set_title(title)
    ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)');ax.set_zlabel('Height (m)')

if __name__=='__main__':
    g=Geometry();a=np.load(OUT/'probe.npz');fig=plt.figure(figsize=(16,10))
    for j,ang in enumerate((-35,50)):
        for i,(title,key) in enumerate((('Original source with robot colliders','wanted'),('Previous reduced target','before'),('Collision/limit constrained candidate','after'))):
            p,r=(a[key][:,:3,3],a[key][:,:3,:3]) if key=='wanted' else g.fk(a[key])
            draw(fig.add_subplot(2,3,j*3+i+1,projection='3d'),g,p,r,title,ang)
    fig.tight_layout();fig.savefig(OUT/'sitting-before-after.png',dpi=130)
