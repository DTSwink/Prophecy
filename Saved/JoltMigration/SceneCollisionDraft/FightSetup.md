# Jolt fight setup

The current priority is the fight sim: characters, weapons, scene collision and blood. Rope, noose and boat work is deferred. The accepted performance checkpoint remains in `Docs/JoltAcceptedPerformance.md`.

## Blueprint startup

1. Call **Initialize Jolt World** once in the gameplay world. It uses that world's gravity; the explicit defaults are 16,384 body slots and seven workers. Check its return value and error. **Is Jolt World Ready** can check an existing world; initialization never resets an existing simulation.
2. Add a **Prophecy Jolt Scene Collision Component** to a persistent gameplay-manager actor and call **Enable Scene Collision**. It imports the loaded static collision into the same world. Preserve this component until the fight ends. Check its pending state and last error when admission is deferred.
3. Once a manual-NN fighter has completed BeginPlay and has its live PhysicalMesh, call **Enable Jolt Physical Animation**. Existing physical-animation targets and PHAT hard limits drive that character. The sword controller selects the fighter's backend for physical equip and drop.

Use supported, authored colliders. The Training sword's previous cooked hull exceeded Jolt's 256 final-vertex limit; the user is redesigning it. No hull simplification is applied automatically.

## Switching a character

**Disable Jolt Physical Animation** returns the character to kinematic presentation. Selecting **Physical** simulation mode afterward enables Chaos again. Selecting Jolt requires the shared world above to be ready. The held sword refreshes its binding when the character backend changes.

This is not a whole-fight state transfer: dropped weapons keep their existing body owner. Choose the backend before starting a fight until transfer of all interacting objects has been implemented and validated.

## Remaining fight acceptance

Run the real sword equip/grip/drop fixture with the redesigned hull, then exercise moving fighters, scene contacts, cutting calls and blood together. The earlier blood fixtures establish static, character and promoted-instance staining; they do not establish the complete live cutting/Niagara path. Finish with one package verification after standalone integration passes.
