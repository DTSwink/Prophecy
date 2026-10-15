"""Build a separate 15-body/34-action humanoid from the verified UEFN PHAT.

No Unreal assets, upstream humanoid or active training files are written.
The companion PHAT adapter is required for exact coupled ball-joint limits.
"""
from pathlib import Path
import copy
import hashlib
import itertools
import json
import sys
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R
import mujoco

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'Saved/MimicKitUEFN/source-rig.json'
if not SOURCE.exists():
    SOURCE = ROOT / 'Saved/Robotics/rig.json'
ORIGINAL = ROOT / 'Saved/MimicKit/vendor/MimicKit/data/assets/humanoid/humanoid.xml'

# Body anchors follow anatomical position, not a cumulative limit invented for
# an omitted chain. Each compound member retains its exact rest-pose transform.
GROUPS = {
    'pelvis': ('pelvis', ['pelvis', 'spine_01', 'spine_02']),
    'torso': ('spine_03', ['spine_03', 'spine_04', 'spine_05', 'clavicle_l', 'clavicle_r']),
    'head': ('neck_01', ['neck_01', 'neck_02', 'head']),
    'right_upper_arm': ('upperarm_r', ['upperarm_r']),
    'right_lower_arm': ('lowerarm_r', ['lowerarm_r']),
    'right_hand': ('hand_r', ['hand_r']),
    'left_upper_arm': ('upperarm_l', ['upperarm_l']),
    'left_lower_arm': ('lowerarm_l', ['lowerarm_l']),
    'left_hand': ('hand_l', ['hand_l']),
    'right_thigh': ('thigh_r', ['thigh_r']),
    'right_shin': ('calf_r', ['calf_r']),
    'right_foot': ('foot_r', ['foot_r']),
    'left_thigh': ('thigh_l', ['thigh_l']),
    'left_shin': ('calf_l', ['calf_l']),
    'left_foot': ('foot_l', ['foot_l']),
}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def transform(t):
    assert np.allclose(t['scale'], 1)
    a = np.eye(4)
    a[:3, :3] = R.from_quat(t['rotation_xyzw']).as_matrix()
    a[:3, 3] = np.array(t['position_cm']) * .01
    return a

def numbers(a):
    return ' '.join(f'{v:.15g}' for v in np.asarray(a).ravel())

def placement(a):
    return dict(pos=numbers(a[:3, 3]), quat=numbers(R.from_matrix(a[:3, :3]).as_quat()[[3, 0, 1, 2]]))

def write_xml(tree, path):
    ET.indent(tree)
    ET.ElementTree(tree).write(path, encoding='utf-8', xml_declaration=True)

def serial_transform(a):
    return dict(position=a[:3, 3].tolist(), quaternion=R.from_matrix(a[:3, :3]).as_quat().tolist())

def shape_size(s):
    if s['kind'] == 'capsule': return [s['radius_cm'] * .01, s['cylinder_length_cm'] * .005]
    if s['kind'] == 'box': return (np.array(s['half_extent_cm']) * .01).tolist()
    if s['kind'] == 'sphere': return [s['radius_cm'] * .01]
    raise ValueError(s['kind'])

def main():
    rig = json.loads(SOURCE.read_text())
    assert rig['success']
    for name, source in rig['source_files'].items():
        assert digest(ROOT / name) == source['sha256'], f'Stale PHAT export: {name}'
    old_hash = digest(ORIGINAL)
    bodies = {b['name']: b for b in rig['bodies']}
    incoming = {rig['bodies'][j['child']]['name']: j for j in rig['joints']}
    owner = {part: name for name, (_, parts) in GROUPS.items() for part in parts}
    assert set(owner) == set(bodies) and sum(len(v[1]) for v in GROUPS.values()) == len(bodies)
    # Proper rotation: UE forward -Y / left +X -> MimicKit forward +X / left +Y.
    basis = np.eye(4); basis[:3, :3] = R.from_euler('z', 90, degrees=True).as_matrix()
    refs = {n: basis @ transform(b['reference']) for n, b in bodies.items()}
    frames = {}
    for name, (anchor, _) in GROUPS.items():
        frames[name] = refs[anchor].copy()
        if name == 'pelvis': frames[name][:3, :3] = np.eye(3)
        else:
            frames[name] = refs[anchor] @ transform(incoming[anchor]['child_frame'])

    tree = ET.parse(ORIGINAL).getroot()
    tree.set('model', 'humanoid_uefn_compound')
    tree.insert(1, ET.Comment('Separate UEFN compound asset. Exact ball limits require limits.json and runtime.py.'))
    tree.find('compiler').set('fusestatic', 'false')
    # User-approved wrist articulation: retain the existing hand bodies and use
    # PHAT frames/limits below. Stock has no wrist actuators; explicitly reuse
    # its neck motor settings (velocity gain 10, effort cap 50 Nm per axis).
    for side in ('right', 'left'):
        hand=tree.find(f".//body[@name='{side}_hand']")
        for axis in ('x','y','z'):
            joint=copy.deepcopy(tree.find(f".//joint[@name='neck_{axis}']"))
            joint.set('name',f'{side}_wrist_{axis}');hand.insert(0,joint)
            motor=copy.deepcopy(tree.find(f"actuator/motor[@joint='neck_{axis}']"))
            motor.set('name',f'{side}_wrist_{axis}');motor.set('joint',f'{side}_wrist_{axis}')
            tree.find('actuator').append(motor)
        # Keep X/Y/Z ordering required by Newton's triple-hinge importer.
        joints=hand.findall('joint')
        for joint in joints:hand.remove(joint)
        for joint in sorted(joints,key=lambda j:j.attrib['name']):hand.append(joint)
    # Jolt uses hard angular stops for these PHAT profiles. Retain the former
    # PHAT adapter's limit regularization, not vanilla humanoid's zero stiffness
    # at the boundary. This remains an iterative constraint, not pose clipping.
    default_joint=tree.find("default/default[@class='body']/joint")
    default_joint.set('solimplimit','.9 .95 .001 .5 2')
    default_joint.set('solreflimit','.02 1')
    parents = {child.attrib['name']: node.attrib['name'] for node in tree.iter('body') for child in node.findall('body')}
    limits = []
    geometry = []
    for node in tree.iter('body'):
        name = node.attrib['name']; anchor, parts = GROUPS[name]
        absolute = frames[name]
        local = np.linalg.inv(frames[parents[name]]) @ absolute if name in parents else absolute
        node.attrib.update(placement(local))
        for geom in list(node.findall('geom')): node.remove(geom)
        # Aggregate the exported effective Jolt inertias with the parallel-axis
        # theorem. Rigidly grouping colliders must not double-count mass.
        masses, centres, tensors = [], [], []
        for part in parts:
            b = bodies[part]
            cm = refs[part] @ transform(b['mass_frame'])
            centre = (np.linalg.inv(absolute) @ cm)[:3, 3]
            ir = absolute[:3, :3].T @ refs[part][:3, :3] @ R.from_quat(b['jolt_inertia_rotation_xyzw']).as_matrix()
            tensor = ir @ np.diag(np.array(b['jolt_inertia_kg_cm2']) * 1e-4) @ ir.T
            masses.append(b['jolt_mass_kg']); centres.append(centre); tensors.append(tensor)
            for k, s in enumerate(b['shapes']):
                world = refs[part] @ transform(s['local'])
                glocal = np.linalg.inv(absolute) @ world
                geom_name = f'{part}_shape{k}'
                ET.SubElement(node, 'geom', name=geom_name, type=s['kind'], size=numbers(shape_size(s)),
                              rgba='.94 .49 .15 1', **placement(glocal))
                geometry.append(dict(name=geom_name, source_body=part, body=name, type=s['kind'],
                                     size=shape_size(s), **serial_transform(world)))
        mass = sum(masses); centre = np.average(centres, axis=0, weights=masses)
        tensor = sum(i + m * ((d @ d) * np.eye(3) - np.outer(d, d))
                     for i, m, p in zip(tensors, masses, centres) for d in [p-centre])
        vals, axes = np.linalg.eigh(tensor)
        if np.linalg.det(axes) < 0: axes[:, 0] *= -1
        im = np.eye(4); im[:3, :3] = axes; im[:3, 3] = centre
        ET.SubElement(node, 'inertial', mass=numbers([mass]), diaginertia=numbers(vals), **placement(im))
        joints = node.findall('joint')
        if not joints: continue
        src = incoming[anchor]
        parent_anchor = rig['bodies'][src['parent']]['name']
        source_parent_frame = refs[parent_anchor] @ transform(src['parent_frame'])
        reference = np.linalg.inv(source_parent_frame[:3, :3]) @ absolute[:3, :3]
        ref_q = R.from_matrix(reference).as_quat()[[3, 0, 1, 2]]
        modes = src['angular_modes_twist_swing2_swing1']
        angles = np.deg2rad(src['angular_limits_deg_twist_swing2_swing1'])
        entry = dict(body=name, source_body=anchor, source_joint=src['name'], modes=modes,
                     limits_rad=angles.tolist(), reference_wxyz=ref_q.tolist(),
                     parent=parents[name], neutral_world=serial_transform(absolute),
                     source_parent_frame=serial_transform(source_parent_frame))
        if len(joints) == 1:
            assert modes == [2, 2, 1], (name, modes)
            rv = R.from_matrix(reference).as_rotvec()
            assert np.linalg.norm(rv[:2]) < 1e-5
            offset = rv[2]
            joints[0].set('axis', '0 0 1')
            joints[0].set('range', numbers([-angles[2]-offset, angles[2]-offset]))
            entry.update(kind='hinge', name=joints[0].attrib['name'], range_rad=[-angles[2]-offset, angles[2]-offset], axis=[0,0,1])
        else:
            assert len(joints) == 3
            for axis, joint in enumerate(joints):
                joint.set('axis', numbers(np.eye(3)[axis]))
                joint.set('limited', 'false')
                joint.attrib.pop('range', None)
            entry.update(kind='ball', name=joints[0].attrib['name'].rsplit('_', 1)[0])
        limits.append(entry)

    # Existing adjacent/compound collisions are handled at body-pair level.
    # Conservatively carry explicit PHAT exclusions through the fixed grouping.
    exclusions = set()
    for a, b in rig['disabled_pairs']:
        x, y = owner[rig['bodies'][a]['name']], owner[rig['bodies'][b]['name']]
        if x != y: exclusions.add(tuple(sorted((x,y))))
    contact = ET.SubElement(tree, 'contact')
    for a,b in sorted(exclusions): ET.SubElement(contact,'exclude',body1=a,body2=b)
    write_xml(tree, HERE/'humanoid_uefn.xml')

    # A direct MuJoCo counterpart mirrors Newton's existing 3-hinge -> ball
    # conversion; it is for geometry/limit validation, not a new articulation.
    physical = copy.deepcopy(tree)
    for node in physical.iter('body'):
        js = node.findall('joint')
        if len(js) != 3: continue
        name = js[0].attrib['name'].rsplit('_', 1)[0]
        first = dict(js[0].attrib); first.update(name=name, type='ball', limited='false')
        first.pop('axis',None); first.pop('actuatorfrcrange',None)
        for j in js: node.remove(j)
        ET.SubElement(node,'joint',**first)
        for axis,j in enumerate(js):
            motor = next(m for m in physical.find('actuator') if m.attrib['joint']==j.attrib['name'])
            magnitude=float(motor.attrib['gear'])
            motor.set('joint',name); motor.set('gear',numbers([magnitude if i==axis else 0 for i in range(6)]))
    write_xml(physical,HERE/'humanoid_uefn_physics.xml')
    model=mujoco.MjModel.from_xml_path(str(HERE/'humanoid_uefn_physics.xml'))
    data=mujoco.MjData(model); mujoco.mj_forward(model,data)
    errs=[]
    for g in geometry:
        ident=model.geom(g['name']).id
        expected=R.from_quat(g['quaternion']).as_matrix()
        actual=data.geom_xmat[ident].reshape(3,3)
        samples=np.array(list(itertools.product((-1,1),repeat=3)),dtype=float)
        if g['type']=='box': samples*=g['size']
        else:
            samples/=np.linalg.norm(samples,axis=1)[:,None]
            samples*=g['size'][0]
            if g['type']=='capsule':samples[:,2]+=np.sign(samples[:,2])*g['size'][1]
        error=np.linalg.norm(samples@actual.T+data.geom_xpos[ident]-(samples@expected.T+g['position']),axis=1).max()
        assert error<1e-9,(g['name'],error)
        errs.append(float(error))
    assert model.nbody-1==15 and model.nv-6==34
    total_mass=sum(b['jolt_mass_kg'] for b in bodies.values())
    assert abs(sum(model.body_mass)-total_mass)<1e-8
    meta=dict(schema=1,model='humanoid_uefn',body_count=15,action_dimensions=34,collider_count=len(geometry),
              wrist_motor_source='User-approved stock neck settings: stiffness100, velocity gain10, effort50Nm, armature0.01; stiffness disabled in velocity mode.',
              source_rig=str(SOURCE.relative_to(ROOT)).replace('\\','/'),
              source_sha256=digest(SOURCE),original_sha256=old_hash,source_files=rig['source_files'],
              basis='UE cm -> metres; +90 degree Z rotation makes UE -Y forward become MimicKit +X.',
              groups={k:dict(anchor=v[0],colliders_from=v[1]) for k,v in GROUPS.items()},
              joints=limits,body_frames={k:serial_transform(v) for k,v in frames.items()},
              source_body_frames={k:serial_transform(v) for k,v in refs.items()},
              source_parents={rig['bodies'][j['child']]['name']:rig['bodies'][j['parent']]['name'] for j in rig['joints']},
              parents=parents,mass_kg=total_mass,geom_surface_max_error_m=max(errs),
              required_limit_adapter='runtime.py:install_limits (coupled PHAT swing/twist, not stock ball cone)',
              collision_exclusions=[list(v) for v in sorted(exclusions)],
              collision_exclusion_note='Body-pair exclusions become coarser when several source bodies share one body.',
              omitted_articulation='spine_01/02/04/05, clavicles, neck_02 and head joint are rigid within their owners; no summed limits.',
              geometry=geometry)
    (HERE/'limits.json').write_text(json.dumps(meta,indent=2))
    # Viewer compares independently evaluated generated geoms against exported
    # PHAT transforms; it never draws the same dataset twice as "verification".
    actual=[]
    for g in geometry:
        ident=model.geom(g['name']).id
        a=dict(g); a.update(position=data.geom_xpos[ident].tolist(),
                          quaternion=R.from_matrix(data.geom_xmat[ident].reshape(3,3)).as_quat().tolist(),
                          size=model.geom_size[ident,:len(g['size'])].tolist())
        actual.append(a)
    om=mujoco.MjModel.from_xml_path(str(ORIGINAL)); od=mujoco.MjData(om); mujoco.mj_forward(om,od)
    root_shift=frames['pelvis'][:3,3]-od.xpos[om.body('pelvis').id]
    old=[]
    types={int(mujoco.mjtGeom.mjGEOM_SPHERE):'sphere',int(mujoco.mjtGeom.mjGEOM_CAPSULE):'capsule',int(mujoco.mjtGeom.mjGEOM_BOX):'box'}
    for i in range(om.ngeom):
        kind=types[int(om.geom_type[i])]; count={'sphere':1,'capsule':2,'box':3}[kind]
        old.append(dict(name=om.geom(i).name,body=om.body(om.geom_bodyid[i]).name,type=kind,
                        size=om.geom_size[i,:count].tolist(),position=(od.geom_xpos[i]+root_shift).tolist(),
                        quaternion=R.from_matrix(od.geom_xmat[i].reshape(3,3)).as_quat().tolist()))
    viewer=dict(meta=meta,phat=geometry,new=actual,old=old)
    (HERE/'overlay-data.json').write_text(json.dumps(viewer,separators=(',',':')))
    assert digest(ORIGINAL)==old_hash
    print(json.dumps(dict(bodies=15,actions=34,colliders=len(geometry),mass_kg=total_mass,
                          max_surface_error_cm=max(errs)*100,old_model_unchanged=True),indent=2))

if __name__=='__main__': main()
