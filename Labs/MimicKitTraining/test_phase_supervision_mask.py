"""Verify excluded feedback rows cannot contribute phase loss or gradients."""
import ast
from pathlib import Path
import torch

tree = ast.parse(Path(__file__).with_name('omni_policy.py').read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'phase_supervision_mse')
scope = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), 'omni_policy.py', 'exec'), scope)
loss = scope['phase_supervision_mse']
prediction = torch.tensor([[1., 2.], [30., 40.], [50., 60.]], requires_grad=True)
target = torch.zeros_like(prediction)
mask = torch.tensor([1., 0., 0.])
value = loss(prediction, dict(next_phase=target, phase_supervision=mask))
torch.testing.assert_close(value, prediction[0].square().mean()/3)
value.backward()
assert torch.equal(prediction.grad[1:], torch.zeros_like(prediction.grad[1:]))
torch.testing.assert_close(prediction.grad[0], prediction.detach()[0]/3)
torch.testing.assert_close(loss(prediction, dict(next_phase=target)), prediction.square().mean())
assert loss(prediction, dict(next_phase=target, phase_supervision=torch.zeros(3))).item() == 0.
print('PASS: feedback phase loss/gradient zero; clock-row weighting unchanged; legacy path unchanged')
from perturbed_motion import getup_head_height_loss
actual = getup_head_height_loss(torch.tensor([1., 1., 1., 1., 2.]), torch.full((5,), 1.5),
    torch.tensor([59, 60, 61, 61, 61]), torch.tensor([True, True, True, False, True]))
torch.testing.assert_close(actual, torch.tensor([0., 0., .25, 0., 0.]))
print('PASS: head-height penalty only after tick60, only perturbed getups, only below target')
