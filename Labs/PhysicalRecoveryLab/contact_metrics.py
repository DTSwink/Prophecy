"""Optional cube-impact measurement for the physical checkpoint viewer."""
import warp as wp


@wp.kernel
def accumulate_cube_impulses(nacon:wp.array(dtype=int),geom:wp.array(dtype=wp.vec2i),world:wp.array(dtype=int),
    addresses:wp.array2d(dtype=int),force:wp.array2d(dtype=float),cube_slots:wp.array(dtype=int),
    rig_geom:wp.array(dtype=bool),dt:float,impulses:wp.array2d(dtype=float)):
    contact=wp.tid()
    if contact>=nacon[0]:return
    pair=geom[contact];slot=int(-1)
    if cube_slots[pair[0]]>=0 and rig_geom[pair[1]]:slot=cube_slots[pair[0]]
    elif cube_slots[pair[1]]>=0 and rig_geom[pair[0]]:slot=cube_slots[pair[1]]
    row=addresses[contact,0]
    if slot>=0 and row>=0:
        w=world[contact];wp.atomic_add(impulses,w,slot,wp.max(0.,force[w,row])*dt)
