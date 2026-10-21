"""Wound-line correction preview; --keep-enabled survives repeated Play sessions.

No asset edits, iteration changes, velocity changes, or native builds. Applies
the same lateral-only translation as ProbePikeSlide --project-wound.
"""
import json, math, pathlib, re, sys, time, traceback, unreal


class PikeWoundDemo:
    def __init__(self, arm=False, keep_enabled=False):
        self.ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        assert keep_enabled or not self.ed.get_game_world(), 'Existing user Play left untouched'
        self.le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/PikeSlide/show-wound-anchor.json'
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.world = None
        self.swords = []
        self.last = None
        self.started = time.monotonic()
        self.arm = arm or keep_enabled
        self.keep_enabled = keep_enabled
        self.first = None
        self.count = 0
        self.max_shift = 0.0
        self.verified = False
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.receipt('enabled across Play sessions' if keep_enabled else
                     'armed for your next Play press' if arm else 'waiting for first cut')
        if not self.arm:
            self.le.editor_request_begin_play()

    def receipt(self, status, **extra):
        self.out.write_text(json.dumps(dict(status=status, corrections=self.count,
            first_cut_time=self.first, max_translation_cm=self.max_shift,
            play_left_running=bool(self.ed.get_game_world()), iterations_changed=False,
            saved_assets=False, keep_enabled=self.keep_enabled, **extra), indent=2), encoding='utf-8')

    def finish(self, status, **extra):
        unreal.unregister_slate_post_tick_callback(self.handle)
        self.handle = None
        self.receipt(status, **extra)
        self.swords.clear()
        self.world = None

    def reset_play(self):
        self.swords.clear()
        self.world = None
        self.last = None
        self.first = None
        self.count = 0
        self.max_shift = 0.0
        self.verified = False
        self.started = time.monotonic()
        self.receipt('enabled; waiting for next Play')

    @staticmethod
    def cross(a, b):
        return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

    @classmethod
    def rotate(cls, q, v):
        c = cls.cross([q.x, q.y, q.z], v)
        d = cls.cross([q.x, q.y, q.z], [c[i]+q.w*v[i] for i in range(3)])
        return [v[i]+2*d[i] for i in range(3)]

    @staticmethod
    def pos(text, name):
        return [float(x) for x in re.search(name+r'=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)', text).groups()]

    def tick(self, dt):
        try:
            w = self.ed.get_game_world()
            if not w:
                if self.world:
                    if self.keep_enabled:
                        self.reset_play()
                    else:
                        self.finish('Play ended; correction retired')
                elif not self.keep_enabled and time.monotonic()-self.started > (600 if self.arm else 30):
                    self.finish('Play startup timeout')
                return
            if self.world is None:
                self.world = w
                self.started = time.monotonic()
                for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
                    if a.get_class().get_name().startswith('A_Sword_C'):
                        sword = next((c for c in a.get_components_by_class(unreal.StaticMeshComponent)
                                      if c.get_name().lower() == 'sword'), None)
                        if sword:
                            self.swords.append((a, sword))
            if w != self.world:
                if self.keep_enabled:
                    self.reset_play()
                else:
                    self.finish('Play world changed; correction retired')
                return
            if not self.keep_enabled and time.monotonic()-self.started > 600:
                self.finish('Ten-minute demo timeout; correction retired')
                return
            t = unreal.GameplayStatics.get_time_seconds(w)
            if t == self.last:
                return
            self.last = t
            for a, sword in self.swords:
                if not unreal.SystemLibrary.is_valid(a) or not unreal.SystemLibrary.is_valid(sword):
                    continue
                if len(a.get_editor_property('cuts')) != 1:
                    continue
                for joint in a.get_components_by_class(unreal.PhysicsConstraintComponent):
                    if joint.get_name() == 'dont':
                        continue
                    c1, b1, c2, b2 = joint.get_constrained_components()
                    if c2 != sword or not c1:
                        continue
                    text = joint.get_editor_property('constraint_instance').export_text()
                    t1 = c1.get_socket_transform(b1, unreal.RelativeTransformSpace.RTS_WORLD)
                    t2 = c2.get_socket_transform(b2, unreal.RelativeTransformSpace.RTS_WORLD)
                    r1 = self.rotate(t1.rotation, self.pos(text, 'Pos1'))
                    r2 = self.rotate(t2.rotation, self.pos(text, 'Pos2'))
                    p1, p2 = t1.translation, t2.translation
                    delta = [p1.x+r1[0]-p2.x-r2[0], p1.y+r1[1]-p2.y-r2[1], p1.z+r1[2]-p2.z-r2[2]]
                    axis = self.rotate(t2.rotation, [0, 0, 1])
                    axial = sum(delta[i]*axis[i] for i in range(3))
                    shift = [delta[i]-axial*axis[i] for i in range(3)]
                    assert all(math.isfinite(x) for x in shift)
                    p = sword.get_world_location()
                    sword.set_world_location(unreal.Vector(p.x+shift[0], p.y+shift[1], p.z+shift[2]), False, True)
                    self.count += 1
                    self.max_shift = max(self.max_shift, math.sqrt(sum(x*x for x in shift)))
                    if self.first is None:
                        self.first = t
                        self.receipt('active', sword=sword.get_path_name())
                    break
            if self.first is not None and not self.verified and t-self.first >= 1.2:
                self.verified = True
                self.receipt('active; first 1.2 seconds verified', game_time=t)
            elif not self.keep_enabled and self.first is None and time.monotonic()-self.started > 60:
                self.finish('No single cut found within timeout')
        except Exception:
            self.finish('error; correction retired', error=traceback.format_exc())


if '--keep-enabled' in sys.argv and 'pike_wound_demo' in globals():
    if pike_wound_demo.handle is not None:
        unreal.unregister_slate_post_tick_callback(pike_wound_demo.handle)
        pike_wound_demo.handle = None
pike_wound_demo = PikeWoundDemo(arm='--arm' in sys.argv, keep_enabled='--keep-enabled' in sys.argv)
print('Wound-line correction enabled across Play sessions, without timeout.' if pike_wound_demo.keep_enabled else
      'Wound-line projection armed for your next Play press.' if pike_wound_demo.arm else
      'Wound-line projection demo started; Play stays open. Stop Play to retire the temporary correction.')
