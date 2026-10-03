from __future__ import annotations

import torch
from torch import nn


class ConditionalDeltaProjector(nn.Module):
    """Predict a clean motion delta from state/control conditioning.

    The complete normalized feature row remains the public input/output shape so
    prior scoring is unchanged. Only the leading motion slice is predicted;
    conditioning values are passed through unchanged and are never scored.
    """

    def __init__(
        self,
        input_dim: int,
        motion_dim: int,
        hidden_dim: int = 1024,
        num_hidden_layers: int = 3,
    ) -> None:
        super().__init__()
        self.input_dim = int(input_dim)
        self.motion_dim = int(motion_dim)
        condition_dim = self.input_dim - self.motion_dim
        if condition_dim <= 0:
            raise ValueError("Conditional projector requires non-motion conditioning")
        layers: list[nn.Module] = []
        width = condition_dim
        for _ in range(int(num_hidden_layers)):
            layers.extend(
                (
                    nn.Linear(width, int(hidden_dim)),
                    nn.LayerNorm(int(hidden_dim)),
                    nn.GELU(),
                )
            )
            width = int(hidden_dim)
        layers.append(nn.Linear(width, self.motion_dim))
        self.projector = nn.Sequential(*layers)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        motion = self.projector(values[:, self.motion_dim :])
        return torch.cat((motion, values[:, self.motion_dim :]), dim=-1)


class ResidualDenoisingDeltaProjector(nn.Module):
    """Full-row denoising projector with an identity-preserving motion skip.

    The public input/output and scored slice are unchanged.  The network sees
    the proposed motion plus its state/control conditioning and predicts only
    the correction.  A zero-initialized final layer makes exact on-manifold
    reconstruction identity at initialization; denoising training then learns
    nonzero corrections for off-manifold proposals.
    """

    def __init__(
        self,
        input_dim: int,
        motion_dim: int,
        hidden_dim: int = 1024,
        num_hidden_layers: int = 3,
    ) -> None:
        super().__init__()
        self.input_dim = int(input_dim)
        self.motion_dim = int(motion_dim)
        self.correction_limit = 0.25
        if self.motion_dim <= 0 or self.motion_dim >= self.input_dim:
            raise ValueError("Residual denoising projector dimensions are invalid")
        layers: list[nn.Module] = []
        width = self.input_dim
        for _ in range(int(num_hidden_layers)):
            layers.extend(
                (
                    nn.Linear(width, int(hidden_dim)),
                    nn.LayerNorm(int(hidden_dim)),
                    nn.GELU(),
                )
            )
            width = int(hidden_dim)
        correction = nn.Linear(width, self.motion_dim)
        nn.init.zeros_(correction.weight)
        nn.init.zeros_(correction.bias)
        layers.append(correction)
        self.correction = nn.Sequential(*layers)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        correction = self.correction_limit * torch.tanh(
            self.correction(values) / self.correction_limit
        )
        motion = values[:, : self.motion_dim] + correction
        return torch.cat((motion, values[:, self.motion_dim :]), dim=-1)


class CalibratedConditionalDeltaProjector(nn.Module):
    """Accepted condition-only projector plus a candidate-aware calibration.

    ``base`` can be initialized from and frozen to an accepted
    :class:`ConditionalDeltaProjector`.  The zero-initialized calibration sees
    the full candidate/context row and removes clean-GT bias without replacing
    the already accepted motion projection.
    """

    def __init__(
        self,
        input_dim: int,
        motion_dim: int,
        hidden_dim: int = 1024,
        num_hidden_layers: int = 3,
    ) -> None:
        super().__init__()
        self.input_dim = int(input_dim)
        self.motion_dim = int(motion_dim)
        self.base = ConditionalDeltaProjector(
            input_dim, motion_dim, hidden_dim, num_hidden_layers
        )
        layers: list[nn.Module] = []
        width = self.input_dim
        for _ in range(int(num_hidden_layers)):
            layers.extend(
                (
                    nn.Linear(width, int(hidden_dim)),
                    nn.LayerNorm(int(hidden_dim)),
                    nn.GELU(),
                )
            )
            width = int(hidden_dim)
        correction = nn.Linear(width, self.motion_dim)
        nn.init.zeros_(correction.weight)
        nn.init.zeros_(correction.bias)
        layers.append(correction)
        self.calibration = nn.Sequential(*layers)

    def freeze_base(self) -> None:
        self.base.eval().requires_grad_(False)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        base_motion = self.base(values)[:, : self.motion_dim]
        motion = base_motion + self.calibration(values)
        return torch.cat((motion, values[:, self.motion_dim :]), dim=-1)


class GatedCalibratedDeltaProjector(nn.Module):
    """Frozen accepted projector with a learned per-channel identity gate."""

    def __init__(
        self,
        input_dim: int,
        motion_dim: int,
        hidden_dim: int = 1024,
        num_hidden_layers: int = 3,
    ) -> None:
        super().__init__()
        self.input_dim = int(input_dim)
        self.motion_dim = int(motion_dim)
        self.base = ConditionalDeltaProjector(
            input_dim, motion_dim, hidden_dim, num_hidden_layers
        )
        layers: list[nn.Module] = []
        width = self.input_dim
        for _ in range(int(num_hidden_layers)):
            layers.extend(
                (
                    nn.Linear(width, int(hidden_dim)),
                    nn.LayerNorm(int(hidden_dim)),
                    nn.GELU(),
                )
            )
            width = int(hidden_dim)
        logits = nn.Linear(width, self.motion_dim)
        nn.init.zeros_(logits.weight)
        nn.init.constant_(logits.bias, -4.0)
        layers.append(logits)
        self.gate_logits = nn.Sequential(*layers)

    def freeze_base(self) -> None:
        self.base.eval().requires_grad_(False)

    def gate(self, values: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.gate_logits(values))

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        base_motion = self.base(values)[:, : self.motion_dim]
        candidate = values[:, : self.motion_dim]
        motion = base_motion + self.gate(values) * (candidate - base_motion)
        return torch.cat((motion, values[:, self.motion_dim :]), dim=-1)
