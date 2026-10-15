"""Read-only recording of actual upstream training body transforms."""
import os
from datetime import datetime, timezone

import mujoco
import numpy as np
import torch
import warp as wp
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from replay import STEPPER, WORLD_TO_VIEW, write_json


class UpstreamReplay:
    def __init__(self, raw, name, capacity=500):
        self.directory = STEPPER/'training/runs'/name
        self.debug = self.directory/'debug'
        self.marker = self.debug/'training.active.json'
        model = raw.sim.mj_model
        root = int(model.jnt_bodyid[np.flatnonzero(model.jnt_type == mujoco.mjtJoint.mjJNT_FREE)[0]])
        ids = [root]
        for i in range(root+1, model.nbody):
            if int(model.body_parentid[i]) in ids:
                ids.append(i)
        body_map = {body: index for index, body in enumerate(ids)}
        self.body_ids = torch.tensor(ids, device=raw.device)
        self.names = [model.body(i).name for i in ids]
        self.bones = [[body_map[int(model.body_parentid[i])], body_map[i]] for i in ids[1:]]
        self.shapes = []
        for i in range(model.ngeom):
            body = int(model.geom_bodyid[i])
            if body not in body_map or not (model.geom_contype[i] or model.geom_conaffinity[i]):
                continue
            kind = int(model.geom_type[i])
            shape = {'bone': self.names[body_map[body]], 'position': model.geom_pos[i].tolist(),
                     'axes': Rotation.from_quat(model.geom_quat[i][[1, 2, 3, 0]]).as_matrix().T.tolist()}
            if kind == mujoco.mjtGeom.mjGEOM_MESH:
                mesh = int(model.geom_dataid[i])
                begin, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
                vertices = model.mesh_vert[begin:begin+count].astype(float)
                hull = ConvexHull(vertices)
                triangles = []
                for face, plane in zip(hull.simplices, hull.equations):
                    a, b, c = vertices[face]
                    if np.dot(np.cross(b-a, c-a), plane[:3]) < 0:
                        b, c = c, b
                    triangles.extend([a.tolist(), b.tolist(), c.tolist()])
                shape.update(kind='mesh', triangles=triangles)
            elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
                shape.update(kind='capsule', radius=float(model.geom_size[i, 0]), length=float(2*model.geom_size[i, 1]))
            elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
                shape.update(kind='sphere', radius=float(model.geom_size[i, 0]))
            elif kind == mujoco.mjtGeom.mjGEOM_BOX:
                shape.update(kind='box', dimensions=(2*model.geom_size[i]).tolist())
            else:
                raise ValueError(f'Unrepresented collision geometry {model.geom(i).name}: {kind}')
            self.shapes.append(shape)
        self.raw = raw
        self.capacity = capacity
        self.count = 0
        self.xpos = wp.to_torch(raw.sim.wp_data.xpos)
        self.xquat = wp.to_torch(raw.sim.wp_data.xquat)
        self.positions = torch.empty((capacity, len(ids), 3), device=raw.device)
        self.quaternions = torch.empty((capacity, len(ids), 4), device=raw.device)
        self.ages = torch.empty(capacity, dtype=torch.int64, device=raw.device)
        self.fps = 1/raw.step_dt
        write_json(self.marker, {'pid': os.getpid(), 'kind': 'upstream_t1'})

    def capture(self):
        i = self.count % self.capacity
        self.positions[i].copy_(self.xpos[0, self.body_ids])
        self.quaternions[i].copy_(self.xquat[0, self.body_ids])
        self.ages[i].copy_(self.raw.episode_length_buf[0])
        self.count += 1

    def publish(self, iteration, checkpoint):
        if self.count < 2:
            return
        ids = torch.arange(max(0, self.count-self.capacity), self.count, device=self.raw.device) % self.capacity
        points = self.positions[ids].cpu().numpy() @ WORLD_TO_VIEW.T
        quats = self.quaternions[ids].cpu().numpy()
        ages = self.ages[ids].cpu().numpy()
        # Keep a contiguous episode. Never interpolate across a training reset.
        cuts = np.flatnonzero(np.diff(ages) <= 0)+1
        start = int(cuts[-1]) if len(cuts) else 0
        end = len(ages)
        if end-start < 2 and len(cuts):
            end, start = start, int(cuts[-2]) if len(cuts) > 1 else 0
        points, quats = points[start:end], quats[start:end]
        if len(points) < 2:
            return
        axes = Rotation.from_quat(quats[..., [1, 2, 3, 0]].reshape(-1, 4)).as_matrix()
        axes = axes.reshape(len(points), len(self.names), 3, 3).swapaxes(-1, -2) @ WORLD_TO_VIEW.T
        n = len(points)
        transitions = self.raw.common_step_counter*self.raw.num_envs
        progress = {'training_transitions': transitions, 'num_envs': self.raw.num_envs,
                    'physics_world_steps': transitions*round(self.raw.step_dt/self.raw.physics_dt)}
        payload = {'schema_version': 2, 'computed_at': datetime.now(timezone.utc).isoformat(),
                   'run_id': self.directory.name, 'step': int(iteration), 'fps': self.fps,
                   'joint_names': self.names, 'bones': self.bones,
                   'rows': [{'row': 0, 'clip_id': 0, 'clip_name': 'T1 · actual training world 0',
                             'clip_path': str(checkpoint), 'start': 0, 'effective_k': n-1,
                             'virtual': False, 'noisy': False, 'has_sword': False,
                             'locomotion_category': 'physical_getup', 'gaze_normalized': [0, 0]}],
                   'positions': [points.tolist()], 'basis': [axes.tolist()],
                   'controller_root_pos': [points[:, 0].tolist()], 'controller_root_rot': [axes[:, 0].tolist()],
                   'frozen_root_pos': [points[:, 0].tolist()], 'frozen_root_rot': [axes[:, 0].tolist()],
                   'source_frame': [list(range(n))], 'source_clip_name': [['actual training world 0']*n],
                   'metadata': {'body_mode': 'full', 'checkpoint_kind': 'upstream_t1',
                                'checkpoint': str(checkpoint), 'has_sword': False,
                                'capture_source': 'actual_training_physics',
                                'physics_hz': 1/self.raw.physics_dt, 'policy_hz': self.fps,
                                'physical_colliders': self.shapes,
                                'display_geometry': 'T1 collision primitives and convex mesh hull',
                                'training_progress': progress, 'step_unit': 'PPO iteration'},
                   'message': 'Actual upstream T1 training motion, including exploration; not a recovery evaluation.'}
        write_json(self.debug/'last_batch_rollout.json', payload)
        write_json(self.directory/'status.json', {'state': 'running', 'iteration': int(iteration),
                                                'updated_at': payload['computed_at'], 'metrics': progress})

    def close(self):
        self.marker.unlink(missing_ok=True)
