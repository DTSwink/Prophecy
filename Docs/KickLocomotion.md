# Kick locomotion controls

**Set Kick Locomotion** has one option: **Non Kicking Foot Loco Drag** (default
false). Configure it before the kick; the active kick retains its entry setting.
Reset Initial Agents restores the saved setting.

When enabled, existing **Set Attack Loco Drag** rules may control the supporting
foot. The main loco-drag feature must also be enabled, and its mode, height,
distance, rotation, pole and handoff settings still apply. The kicking foot stays
attack-owned. Once the supporting foot hands over, it does not reacquire drag
ownership during that attack.

Kicks always use full-body mode. Trigger NN Attack with Half Attack checked still
starts a full kick, and Set NN Half Attack Enabled ignores half requests while
kicking. There is no kick half threshold, countdown, thigh target-mounting regime,
partial lower-body return or Hit-triggered leg release.

## Hidden running leg

While supporting-foot drag remains active, the locomotion NN receives a hidden
running version of the kicking leg. The existing lower prediction advances it;
no extra NN evaluation is performed. Both prior/current leg states are retained,
so ankle position, foot/thigh rotation, toe bend and derived velocity describe
locomotion rather than the visible kick. The actual pelvis and accepted supporting
leg remain shared. Physical resampling cannot replace this hidden leg with the
simulated kicking limb. Root/capsule coordinate changes rebase its history without
moving it in world space.

The visible kicking leg and independent attack model keep performing the attack.
Ghost Loco Drag is a separate feature shielding the attack prediction from real
dragged legs. Full drag completion, attack end/retarget and reset discard the hidden
running history. The handoff seeds actual visible endpoints so a hidden pose never
appears on the mesh. Other attack families and kicks without supporting-foot drag
keep their prior behavior.

The retired H-A pin is removed from existing Set Kick Locomotion nodes by
`Prophecy.Editor.RemoveKickHalf`, preserving the checkbox and remaining wiring.

Focused native tests: `Prophecy.NN.KickLocomotion.State`, `.RunGhost`, and
`Prophecy.NN.AttackEntry.FootLocomotion` (including handoff/pole coverage).
