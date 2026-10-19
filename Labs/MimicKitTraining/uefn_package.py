"""One source inventory for UEFN packaging and pre-spend stale-source checks."""
from pathlib import Path

CONTACT_FILES=('contact_engine.py','sequential_contact_adapter.py','sequential_contact_gpu.py',
               'block_contact_gpu.py','coupled_contact_gpu.py','contact_manifolds_gpu.py','jolt_limit_directions.py',
               'limit_projection_gpu.py','floor_projection_guard.py','floor_projection_parallel.py','solver_capture.py')


def runtime_files(root):
    root=Path(root)
    return {
        **{'pipeline/'+name:root/'Labs/MimicKitTraining'/name for name in
           ('train.py','resume.py','kl_guard.py','uefn_engine.py','native_uefn_engine.py','torque_envelope.py','omni_walk.py','fused_kinematics.py','recovery_omni.py','omni_policy.py','absolute_walk.py','flat_com.py','observe.py','observe_many.py','omni_config.py','health.py','uefn_package.py')},
        **{'assets/uefn/'+name:root/'Labs/MimicKitUEFN'/name for name in
           ('humanoid_uefn.xml','limits.json','physics.json','runtime.py','velocity_motors.py','body_velocity.py')},
        'assets/PhysicalRecoveryLab/phat_constraints.py':root/'Labs/PhysicalRecoveryLab/phat_constraints.py',
        **{'assets/MimicKitTransfer/'+name:root/'Labs/MimicKitTransfer'/name for name in CONTACT_FILES},
    }


def verify_package(package,root):
    for entry,path in runtime_files(root).items():
        assert package.read(entry)==path.read_bytes(), 'Stale UEFN runtime: rebuild source.zip ('+entry+')'
