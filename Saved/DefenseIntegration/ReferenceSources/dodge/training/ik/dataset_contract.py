from __future__ import annotations

from pathlib import Path

try:
    from .bootstrap import PROJECT_ROOT
except ImportError:
    from bootstrap import PROJECT_ROOT


REDUCED_PERIODIC_NPZ = (PROJECT_ROOT / "ue5" / "animations_omni_only" / "npz_final").resolve()
LEGACY_FULL_PERIODIC_NPZ = (PROJECT_ROOT / "ue5" / "animations_omni_only_full" / "npz_final").resolve()
REDUCED_TRANSITION_NPZ = (PROJECT_ROOT / "ue5" / "animation_transitions_only_full" / "npz_final_trimmed").resolve()
LEGACY_FULL_TRANSITION_NPZ = (PROJECT_ROOT / "ue5" / "animations_transitions_only_full_trimmed" / "npz_final").resolve()

_LEGACY_TO_REDUCED = {
    LEGACY_FULL_PERIODIC_NPZ: REDUCED_PERIODIC_NPZ,
    LEGACY_FULL_TRANSITION_NPZ: REDUCED_TRANSITION_NPZ,
}

_COMPLETENESS_PAIRS = (
    ("periodic", REDUCED_PERIODIC_NPZ, LEGACY_FULL_PERIODIC_NPZ),
    ("nonperiodic", REDUCED_TRANSITION_NPZ, LEGACY_FULL_TRANSITION_NPZ),
)


def _npz_stems(folder: Path) -> set[str]:
    return {path.stem for path in folder.glob("*.npz")}


def audit_npz_folder(folder: Path) -> None:
    resolved = folder.resolve()
    replacement = _LEGACY_TO_REDUCED.get(resolved)
    if replacement is not None:
        raise RuntimeError(
            "Refusing legacy full-body NPZ folder for current reduced IK training: "
            f"{resolved}. Use {replacement} instead. "
            "This is a hard error so we never silently train a 986->443/1429-dim model."
        )

    for label, reduced, legacy in _COMPLETENESS_PAIRS:
        if resolved != reduced or not legacy.exists():
            continue
        missing = sorted(_npz_stems(legacy) - _npz_stems(reduced))
        if missing:
            raise RuntimeError(
                f"Reduced {label} NPZ folder is missing {len(missing)} clips present in {legacy}: "
                f"{', '.join(missing)}. Regenerate/copy them before training; do not proceed on a silent subset."
            )
