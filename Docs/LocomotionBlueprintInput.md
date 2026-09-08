# Blueprint-owned locomotion input

**Verified in `testNN`:** all 13 public-node checks pass, including inactive native keys,
persistent input, gait changes, braking, analog strength, scales, strafing, yaw-only,
diagonal normalization and preserved idle facing. The mover reaches 200.0018 cm/s Walk,
500 cm/s Run and 100.0009 cm/s at half walk stick. Regression:
`Tools/NN/TestProphecyLocomotionInput.py`; results: `Saved/LocomotionInput/runtime.json`.

All nodes below belong to **Prophecy Agent** (`Self` inside `BP_ProphecyManualPoseAgent`).
Native Z/S/Q/D and Shift polling has been removed. No keyboard bindings, camera graphs,
possession settings or maps are changed. The existing 30 Hz mover still handles
acceleration, braking, turning, capsule sweeps and the NN's future-root window.
An unwired manual agent has zero stick. Ordinary crowd routes/bridge intent remain available.

## Nodes and variables

| Node | Pins / use |
|---|---|
| **Set Locomotion Input** | **World Move Input**: world XY direction times stick strength; length 0 = stop, 0.5 = half stick, 1 = full stick. Z is ignored and lengths above 1 are clamped. **Run**: false = Walk, true = Run. **Facing World Direction**: independent world XY direction; zero preserves the existing facing target. **Speed Scale**, **Turn Scale**: 0..1, default 1. No Delta Seconds input. |
| **Set Locomotion Running** | **Run** changes only Walk/Run; preserves the current stick, facing and scales. Useful for Shift pressed/released. |
| **Stop Locomotion Input** | Zeroes the stick and preserves the facing target. Uses normal mover braking; does not teleport or zero the capsule's velocity. Preserves the selected gait and scales. |
| **Get Locomotion Input** | Returns the stored **Prophecy Locomotion Input** struct. Split its pin or use **Break Prophecy Locomotion Input** to read the five input fields above. These are requested inputs, not measured movement. |
| **Get Locomotion State** | Returns measured **World Velocity Cm Per Second**, actual **Facing World Direction**, and the currently active **Run** flag. Return Value is false before this agent has a registered mover. Velocity is horizontal, from the fixed-step mover after collision resolution, not interpolated mesh motion. |
| **Get Locomotion Target** | Returns **Target World Velocity Cm Per Second**, scalar **Target Speed Cm Per Second**, **Target Facing World Direction**, and **Run** from the most recently completed mover step. This is the goal before acceleration/braking, including stick/scales, directional gait limits, run turn-speed boost and attack overrides. Facing is the final goal, not the current partly turned direction. Return Value is false until the first mover step. |
| **Get Agent Camera** / **Get Agent Spring Arm** | Existing references to your camera components; camera rotation remains yours to implement. |

Exposed variables:

- **Locomotion Input**: the same five-field struct, editable/read-write in Blueprint. You can use **Set Members in Prophecy Locomotion Input** on the variable instead of the convenience nodes.
- **Use Blueprint Locomotion Input**: setters enable this automatically. Enable it yourself if writing the struct directly. This agent's Blueprint inputs take precedence over automatic route/bridge intent. Disabling it returns ownership to the original crowd/bridge path; a simple manual test agent idles instead.

Inputs persist until changed and can be stored before manager registration, including in BeginPlay.
Setters do not reseed NN state or bypass the mover. Full-body NN attacks still temporarily suppress
movement; the stored Blueprint request is retained and resumes after the attack.
No per-agent timer or Blueprint Tick is required just to keep a constant input active.

**Current versus target:** use **Get Locomotion State** to read what the capsule is doing;
use **Get Locomotion Target** to read what the mover is trying to reach. For example,
after releasing movement the target speed is zero while current speed is still braking.
The target getter reads a small cached snapshot from the actual 30 Hz step; it does not
run prediction or NN inference. Calling an input setter does not update that snapshot
until the next mover step. When inference is disabled, it retains the last completed step.
The facing output is a world-space unit vector: feed it to **Make Rot from X** if you
need a conventional direction Rotator; this does not apply the mannequin's capsule/mesh
axis offset for you.

## Reproduce Z/S/Q/D + Shift, relative to your camera

1. Keep the placed agent's existing **Auto Possess Player = Player 0** setup. Create four local Boolean variables `Z Held`, `S Held`, `Q Held`, `D Held` and one `Run Held`, all false.
2. Create your own Blueprint function `Update Movement Input`:
   - `ForwardAxis = (Z Held ? 1 : 0) - (S Held ? 1 : 0)`.
   - `RightAxis = (D Held ? 1 : 0) - (Q Held ? 1 : 0)`.
   - From **Get Agent Camera**, get **Forward Vector** and **Right Vector**. For each, use **Break Vector**, **Make Vector** with Z = 0, then **Normalize**. Call them `Flat Forward` and `Flat Right`.
   - `World Move = Flat Forward * ForwardAxis + Flat Right * RightAxis`.
   - Call **Set Locomotion Input** with `World Move Input = World Move`, `Run = Run Held`, both scales = 1.
   - When `World Move` is nonzero, use `Facing World Direction = Flat Forward`. When it is zero, use `(0,0,0)`. This reproduces camera-facing strafing while moving and preserves the previous facing target at idle. The node limits diagonals to full stick automatically.
3. For each of Z/S/Q/D: **Pressed** sets its Held Boolean true; **Released** sets it false. After either event, call `Update Movement Input`. Tracking each key separately keeps opposite keys and partial releases correct.
4. **Shift Pressed**: set `Run Held = true`, then **Set Locomotion Running(true)**. **Shift Released**: set it false, then **Set Locomotion Running(false)**. Keep `Run Held` updated because the next full input call also supplies Run. If both Shift keys are supported, track each separately and OR them.
5. After your camera rotation code changes the camera, call `Update Movement Input` while a movement key is held. A stored world vector does not automatically rotate with the camera. At idle, do not supply the camera direction as facing: zero facing lets the camera orbit without turning the body.
6. Release all movement keys: the next `Update Movement Input` sends zero stick and the mover brakes normally. Send **Stop Locomotion Input** as well when opening a menu/disabling your input so a held request cannot remain active accidentally.

To face the travel direction instead of strafing, feed normalized `World Move` to **Facing World Direction**.
To turn in place, deliberately send zero **World Move Input** and a nonzero **Facing World Direction**.
For analog input, substitute your input action's two axes for the four-key calculation.

Do not multiply these inputs by Delta Seconds or set actor location/velocity yourself.
Use these nodes, not Unreal's generic **Add Movement Input**: this pawn uses the project's
existing mover, not CharacterMovement or FloatingPawnMovement. Epic's
[Add Movement Input documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/Pawn/Input/AddMovementInput)
also distinguishes collecting Pawn input from actually implementing its movement.
