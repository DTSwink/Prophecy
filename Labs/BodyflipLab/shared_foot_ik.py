"""Serve the canonical Foot IK modules without copying them or sharing app state."""
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / 'FootIKLab'
MODULES = ('recovery.js', 'support.js', 'terrain.js', 'footik.js', 'surface.js')


def bundle():
    sources = [(name, (SOURCE / name).read_text(encoding='utf-8')) for name in MODULES]
    digest = hashlib.sha256(''.join(name + text for name, text in sources).encode()).hexdigest()
    factories = ',\n'.join(json.dumps(name) + ':function(module,exports,require){\n' + text + '\n}' for name, text in sources)
    return ("/* Live FootIKLab source; generated on request, never a saved copy. */\n"
            "(function(){'use strict';const factories={" + factories + "},cache={};\n"
            "function load(name){name=name.replace(/^\\.\\//,'');if(cache[name])return cache[name].exports;"
            "if(!factories[name])throw Error('Unknown shared Foot IK module: '+name);"
            "const module={exports:{}};cache[name]=module;factories[name](module,module.exports,load);return module.exports;}\n"
            "globalThis.SharedFootIK={surface:load('surface.js'),sourceHash:" + json.dumps(digest) + "};})();\n").encode()
