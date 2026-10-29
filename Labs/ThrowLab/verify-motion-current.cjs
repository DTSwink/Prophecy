// Audit a copy of the current saved scene in an isolated headless viewer.
// Uses the existing lab service; never writes state.json or opens a desktop tab.
process.env.THROW_DYNAMICS_TAG='before';
process.env.THROW_MOTION_AUDIT='1';
require('./verify-attack-ui.cjs');
