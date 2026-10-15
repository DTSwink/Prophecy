"""Stock AMP with a static reference and fixed upright/floor reset cohorts."""
import math
from pathlib import Path
import torch
from envs.amp_env import AMPEnv
from envs.base_env import DoneFlags
from util import torch_util
from replay import geometry


class StandingAMPEnv(AMPEnv):
    task_name = 'amp_standing'

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        n = self.get_num_envs()
        # Fixed identities: frequent upright failures never move worlds into
        # the floor cohort. World zero remains a floor world for the replayer.
        fraction = config.get('upright_cohort_fraction', .2)
        assert 0 <= fraction <= 1
        self._upright_cohort = torch.arange(n, device=self._device) >= n-round(fraction*n)
        self._starts_on_back = torch.zeros(n, device=self._device, dtype=torch.bool)
        self._reset_rng = torch.Generator(device=self._device).manual_seed(config['reset_seed'])
        self._noise = math.radians(config['reset_joint_noise_degrees'])
        self._clearance = config['reset_floor_clearance_m']
        lo, hi = self._engine.get_obj_dof_limits(0, self._get_char_id())
        self._limits = [torch.as_tensor(v, device=self._device,dtype=torch.float32) for v in (lo,hi)]
        g = geometry(Path(config['char_file']))
        shapes = g['shapes']
        tensor = lambda v: torch.tensor(v, device=self._device, dtype=torch.float32)
        self._shape_bodies = torch.tensor([g['names'].index(s['bone']) for s in shapes], device=self._device)
        self._shape_centers = tensor([s['position'] for s in shapes])
        self._shape_axes = tensor([s['axes'] for s in shapes])
        self._shape_radii = tensor([s.get('radius',0.) for s in shapes])
        self._shape_extents = tensor([s['dimensions'] if s['kind']=='box' else [0.,0.,s.get('length',0.)] for s in shapes])*.5

    def _lowest_geometry(self, body_pos, body_rot):
        q = body_rot[:,self._shape_bodies]
        centers = body_pos[:,self._shape_bodies]+torch_util.quat_rotate(q,self._shape_centers.expand(q.shape[0],-1,-1))
        axes = torch_util.quat_rotate(q[:,:,None,:].expand(-1,-1,3,-1),self._shape_axes.expand(q.shape[0],-1,-1,-1))
        extent = (axes[:,:,:,2].abs()*self._shape_extents).sum(-1)+self._shape_radii
        return (centers[:,:,2]-extent).amin(-1)

    def _reset_char(self, env_ids):
        super()._reset_char(env_ids)
        ids = env_ids[~self._upright_cohort[env_ids]]
        n = ids.numel()
        if not n: return
        char = self._get_char_id()
        back = torch.rand(n,device=self._device,generator=self._reset_rng)<.5
        self._starts_on_back[ids] = back
        r = torch.zeros(n,3,device=self._device)
        r[:,1] = torch.where(back,-math.pi/2,math.pi/2)
        rotation = torch_util.exp_map_to_quat(r)
        noise = (2*torch.rand((n,self._init_dof_pos.numel()),device=self._device,generator=self._reset_rng)-1)*self._noise
        dofs = (self._init_dof_pos+noise).clamp(*self._limits)
        root = self._init_root_pos.expand(n,-1).clone()
        pos,rot = self._kin_char_model.forward_kinematics(root,rotation,self._kin_char_model.dof_to_rot(dofs))
        root[:,2] += self._clearance-self._lowest_geometry(pos,rot)
        self._engine.set_root_pos(ids,char,root)
        self._engine.set_root_rot(ids,char,rotation)
        self._engine.set_dof_pos(ids,char,dofs)

    def _reset_disc_hist(self, env_ids):
        # The static demo is NOT the past of a fallen agent. Fill all history
        # slots with the actual reset pose and zero reset velocities.
        char = self._get_char_id()
        root = self._engine.get_root_pos(char)[env_ids]
        rot = self._engine.get_root_rot(char)[env_ids]
        joints = self._kin_char_model.dof_to_rot(self._engine.get_dof_pos(char)[env_ids])
        bodies,_ = self._kin_char_model.forward_kinematics(root,rot,joints)
        values = dict(root_pos=root,root_rot=rot,joint_rot=joints,body_pos=bodies,
            root_vel=self._engine.get_root_vel(char)[env_ids],
            root_ang_vel=self._engine.get_root_ang_vel(char)[env_ids],
            dof_vel=self._engine.get_dof_vel(char)[env_ids])
        for name,value in values.items():
            history = value[:,None].expand(-1,self._num_disc_obs_steps,*value.shape[1:])
            getattr(self,'_disc_hist_'+name).fill(env_ids,history)

    def _update_done(self):
        super()._update_done()
        # Keep vanilla failure semantics for upright worlds; floor worlds
        # retain the vanilla timeout (and its bootstrapping), never fake success.
        floor = ~self._upright_cohort
        self._done_buf[floor] = torch.where(self._time_buf[floor]>=self._episode_length,
            DoneFlags.TIME.value,DoneFlags.NULL.value).to(self._done_buf.dtype)


from networks import register_network  # Compatibility for existing AMP launchers/tests.
