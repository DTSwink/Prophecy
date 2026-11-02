"""Candidate: omit unread intermediate body reconstructions, preserving both states."""
from contextlib import contextmanager
import inspect
import warp as wp


class DeferredFK:
    def __init__(self, engine):
        self.engine = engine
        assert engine._sim_steps == 8
        assert not engine._visualize()
        assert not getattr(engine, '_track_ground_contact_peaks', False)
        assert engine._control_mode.name == 'vel'
        assert engine._solver.mjw_model.opt.run_collision_detection
        method = type(engine._solver)._update_newton_state
        self.kernel = method.__globals__['eval_articulation_fk']
        self.calls = 0
        self.skipped = 0
        self.dirty = set()
        self.output_elements = 0
        self.original = wp.launch
        self.signature = inspect.signature(wp.launch)

    def launch(self, *args, **kwargs):
        bound = self.signature.bind(*args, **kwargs)
        kernel = bound.arguments['kernel']
        inputs = bound.arguments.get('inputs') or []
        outputs = bound.arguments.get('outputs') or []
        read_pointers = {v.ptr for v in inputs if isinstance(v, wp.array)}
        bad = self.dirty.intersection(read_pointers)
        assert not bad, f'Intermediate FK result is consumed by {kernel.key}'
        if kernel is self.kernel:
            index = self.calls
            self.calls += 1
            assert index < 8
            if index < 6:
                self.skipped += 1
                self.dirty.update(v.ptr for v in outputs)
                return
            self.dirty.difference_update(v.ptr for v in outputs)
        return self.original(*args, **kwargs)

    @contextmanager
    def capture(self):
        self.calls = self.skipped = 0
        self.dirty.clear()
        previous = wp.launch
        self.original = previous
        try:
            wp.launch = self.launch
            yield self
            assert self.calls == 8 and self.skipped == 6 and not self.dirty
        finally:
            wp.launch = previous
