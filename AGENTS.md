# Prophecy handoff

For Unreal and game-related labs, read `ProjectJournal.md` first. Its opening
status and golden rules are the current handoff; dated archives are historical
and can contain superseded settings/build instructions. Read the linked topic
for the area being changed.

For standalone policy/AE training, datasets, cloud GPU runs, sweeps, checkpoints,
TensorBoard and training replayers, read `TrainingJournal.md` first, then the
relevant training topic. Update that journal and topic docs, not ProjectJournal.md.
Only actual Unreal integration, asset/Blueprint/runtime/build changes or native
compatibility contracts belong in the game journal; link training evidence there
instead of copying experiment logs. Game-related labs already tied to native
systems (Bodyflip, Foot IK, reach/grab, etc.) retain their Unreal handoff.

Preserve the user's Blueprint wiring, tuning, assets and active Play session.
Use the existing remote Python tooling for Unreal. Private retained C++ layout
changes require a normal build and restart, not Live Coding. See the game journal
for the complete save/build/verification procedure and standing authorizations.

For facial expressions (baked face morphs, wrinkle textures, face material/curve
hookup), read `FaceJournal.md` first; it owns that work. Do not log it in
ProjectJournal.md beyond a link.
