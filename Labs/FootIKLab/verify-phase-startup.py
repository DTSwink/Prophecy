"""Bounded cache/lifetime checks, without importing Torch or starting workers."""
import ast
import hashlib
import json
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(tree, str(path), 'exec'), namespace)


with tempfile.TemporaryDirectory(prefix='footik-seed-check-') as folder:
    root = Path(folder)
    (root/'models').mkdir()
    for name in ('locomotion.py', 'models/provenance.json', 'native.py'):
        (root/name).write_text('original', encoding='utf-8')
    native = types.SimpleNamespace(__file__=str(root/'native.py'))
    native.lower_ctl = native
    generate = Mock(return_value={'poses': ['original-seed'], 'roots': [0, 1]})
    ns = dict(ROOT=root, MODEL_ROOT=root, Path=Path, json=json, hashlib=hashlib, STRIDE_TICKS={'run': 38},
              inspect=types.SimpleNamespace(getsource=lambda fn: 'unchanged seed implementation'),
              torch=types.SimpleNamespace(__version__='test'), generate=generate,
              decode_policy_rows=None, configure_direction=None,
              runtime_data=native, upper_ctl=native, upper_data=native, cached_data=native, tl=native)
    load_functions(ROOT/'directional_nn.py', {'command_seed'}, ns)
    def owner():
        return types.SimpleNamespace(gait='run-forward', direction='forward', direction_sources={'sourceSha256': 'original'})
    first = owner()
    expected = ns['command_seed'](first)
    assert ns['command_seed'](first) is expected and generate.call_count == 1
    assert ns['command_seed'](owner()) == expected and generate.call_count == 1
    (root/'native.py').write_text('changed codec', encoding='utf-8')
    ns['command_seed'](owner())
    assert generate.call_count == 2
    (root/'models/provenance.json').write_text('changed weights', encoding='utf-8')
    ns['command_seed'](owner())
    assert generate.call_count == 3
    changed = owner(); changed.direction_sources['sourceSha256'] = 'changed geometry'
    ns['command_seed'](changed)
    assert generate.call_count == 4
    ns['command_seed'](owner(), True)
    assert generate.call_count == 5
    (root/'.nn-cache/seed-run-forward--1.json').write_text('interrupted', encoding='utf-8')
    ns['command_seed'](owner())
    assert generate.call_count == 6
    ns['STRIDE_TICKS']['run'] = 40
    ns['command_seed'](owner())
    assert generate.call_count == 7

import nn_service
with patch.object(nn_service.threading, 'Timer') as factory, patch.object(nn_service, '_stop') as stop:
    first, second = Mock(), Mock()
    factory.side_effect = [first, second]
    nn_service.timer = None
    nn_service._schedule_retirement()
    assert factory.call_args.args[0] == 300
    first.start.assert_called_once()
    nn_service._schedule_retirement()
    first.cancel.assert_called_once()
    nn_service._retire(first)
    stop.assert_not_called()
    nn_service._retire(second)
    stop.assert_called_once()
    assert nn_service.timer is None
print('PASS: seed reuse/invalidation/recovery; bounded idle lifetime and stale-timer protection.')
