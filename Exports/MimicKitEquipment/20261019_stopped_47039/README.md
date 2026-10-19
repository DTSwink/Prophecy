# Stopped equipment policy — October 19, 2026

Final evaluated checkpoint: **47039 / 770,703,360 samples**. The owned L4 pod
`n5esp2rc3dvxc4` is stopped (`EXITED`). Local checkpoint SHA256 matches the
verified persistent S3 object; details are in `manifest.json`.

`checkpoint_0047039_final.zip` includes model weights, Adam optimizer state,
normalizers, counters/RNG state, engine/environment/agent configurations,
final evaluation, replay, TensorBoard events and training log. Resumption
starts new physical episodes; the live simulator state is not serialized.

`training_source.zip` is the exact deployed source package, including the
training wrappers, physics model, motion data and prepared configuration.
Use this package to reproduce the deployed asset versions: the live workspace
PHAT may have been edited since deployment. Base MimicKit commit is recorded
in the manifest; dependency versions are in checkpoint `runtime-freeze.txt`.
The separately committed Labs sources also preserve later diagnostic helpers.

Configuration: 512 agents, configured native MJWarp, 240 Hz physics / 30 Hz
policy, 1024 -> 1024 -> 512 networks, velocity control and reciprocal reward.
Position allowances are 10 cm horizontal / 5 cm vertical for idle/get-up legs,
5 cm spherical for their upper body, and 3 cm spherical for locomotion.
See Docs/MimicKitTraining.md for the full training history and resumption tools.

Training is stopped intentionally; downloading or checking out these files
must not start a paid GPU session automatically.
