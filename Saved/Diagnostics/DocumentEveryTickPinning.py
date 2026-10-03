from pathlib import Path
p=Path('Docs/WalkPinningEveryTick.md');p.write_text('''# Temporary every-tick Walk pinning comparison

`Set Walk Pinning Every Tick` takes Agent and Enabled. Off by default. Use together with the existing `Set Walk Pinning Smoothing` node: it retains the existing independent Pin In/Pin Out counts. One frame means the next unpaused game tick; 60 ticks means one authored second regardless of wall framerate. Repeated calls do not restart smoothing.

The ordinary path samples the smooth state only at NN evaluations. The experimental path also resamples the cached Walk foot-roll displacement on intermediate game ticks, using the latest available decision and the current smoothing value. No extra NN inference, policy step, root advance, recurrence update, or blend-clock advance occurs. This is a presentation experiment; the existing policy correction still supplies recurrent history at its usual cadence.

Per-foot caches retain previous/current policy displacement, sampled weight, mixed Walk contribution, and the latest spatial caps/transfer minimum. Bounds and full-extension rejection keep priority. Only the eight leg component/local transforms are republished; upper body, pose source time, root carriers and foot rotations are preserved except existing connected-leg/clamp requirements. Existing calf/foot clamps and connected recovery solve are reused; their algorithms are not edited. Hermite endpoint corrections transport tangents linearly and are reversible.

Debug effective pin comes from the same resampling; raw NN decision remains the latest policy sample. Disabling restores cached original legs immediately and removes experiment state. Turning smoothing off, specials, pure Run and reset clear cached poses; the toggle configuration can remain enabled for later Walk. Disabled has no cached pose, timer, correction/decoding work or extra inference, only the empty-map guard.

Original current-scene capture: at527 raw left0 requests unpinning but applied1,528 debug retains1 despite smoothing reaching0,529 raw left1 but applied0. Blueprint smoothing is In3/Out1, backward bound40–55cm/root7/LerpTarget.75; reach guard is disconnected. Baseline evidence: Saved/Diagnostics/Pin529Baseline.json and Pin529BP.copy.

Build and validation pending.
''',encoding='utf-8')
