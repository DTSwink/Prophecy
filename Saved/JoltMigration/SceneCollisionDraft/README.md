# Opt-in scene collision draft

Status: source draft only; no active project edits, build or Unreal run by this agent. Root's separately owned `rootapi` directory is untouched.

Apply the four files in `proposed/Source/GameAnimationSample3` after reviewing the coordinator against its saved `baseline`. The coordinator change adds one include and prepares the single scene owner in a second pass immediately before the existing native step. Other client interfaces and step ownership are unchanged.

`UProphecyJoltSceneCollisionComponent` requires an initialized synchronous Game/PIE Jolt world and uses the existing safe client admission. Enable/disable are explicit Blueprint calls; pending status, enabled status and the last error are BlueprintPure. The component is passive and creates no tick or independent native step. One enabled or pending scene owner is allowed per world.

Initial admission scans loaded visible levels once for static primitive sources. Native actor spawn, level addition/removal, physics create/destroy, transform and collision-setting notifications queue source reconciliation. ISM/HISM index changes and tree completion queue full recapture. Because individual instance transform edits have no public notification, the owner compares only retained eligible ISM transforms before each shared step; it does not scan the world each frame. Zero-scale instances retire their native handle; individual transform edits preserve unchanged neighbor handles; reindexing recaptures with fresh generations. Final static mesh receivers spawned by blood promotion enter through the normal source lifecycle.

Only the existing strict static importer supplies geometry and simulation settings. Query-only/no-collision sources remain observed without being imported. Unsupported eligible collision stops admission or the shared step with its exact source path and instance index. Original UE collision, query receivers and assets are never rewritten. A runtime error retains owner state for explicit cleanup; disable/end-play/unregister remove callbacks and owned native bodies.

Focused verification draft: `Prophecy.Jolt.SceneCollision.ISMPromotionAndCleanup`. It uses the real engine Cube collision, a static floor, two actual native ISM bodies and one dynamic body component sharing the coordinator. It checks zero-scale retirement plus a spawned promoted receiver before the shared step, exact unchanged neighbor ownership, native and UE query receiver identity, reindex invalidation and cleanup preserving UE sources. This test has not been compiled or run yet. No performance benchmark is included.

Scope remains fight simulation. No rope, boat, noose, global backend switch, dynamic importer relaxation, hull simplification or asset change is introduced.
