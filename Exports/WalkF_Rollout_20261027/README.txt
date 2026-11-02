WalkF complete rollout, 27 October 2026

walkf_rollout.mp4: two-camera rendered preview of the full 121-frame sequence.
walkf_rollout.npz: world positions and rotations, skeleton, body mask and pin values.
metadata.json: source/checkpoint hashes, settings and coordinate conventions.

Generated fresh through the unmodified Model Viewer inference pipeline using
its default Pin Constraint and Run near-floor pin settings. The open viewer
was not altered. This is a rendered export, not a screen recording or a dump
of unsaved in-memory UI tweaks. Frames 0/1 seed the autoregressive rollout;
frames 2 through 120 are inferred. Preview cameras follow horizontal motion;
NPZ retains the actual world-space translation. This is a LOWER-BODY policy:
use visible_bone_indices for the nine meaningful pelvis/leg/foot joints. Other
raw FK slots are retained only for completeness, not a valid upper-body motion.
